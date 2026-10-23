"""Prometheus metrics for the LLM runtime, with cardinality kept on a leash.

Rules of thumb baked in here:

* Label values come from a closed set. Team and model labels are checked
  against an allowlist; anything else becomes "other". User IDs, key IDs,
  request IDs and prompts are never labels (that's what traces/logs are for).
* Histogram buckets are chosen for LLM latencies (tens of ms to a minute),
  not the default web buckets that top out at 10s.
* Cost is a counter in USD so `rate()` gives $/s per team and model, which is
  what the budget burn alert keys off.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prometheus_client import CollectorRegistry, Counter, Histogram

LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60)
TTFT_BUCKETS = (0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)
TOKEN_BUCKETS = (16, 64, 256, 1024, 4096, 16384)


@dataclass
class CardinalityGuard:
    teams: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    backends: set[str] = field(default_factory=set)
    overflow: str = "other"

    def team(self, value: str | None) -> str:
        return value if value in self.teams else self.overflow

    def model(self, value: str | None) -> str:
        return value if value in self.models else self.overflow

    def backend(self, deployment_id: str | None) -> str:
        # Deployment ids are "<group>-<backend>" (model_info.id in config.yaml),
        # which stays the same whatever hostnames the environment uses.
        backend = (deployment_id or "").rsplit("-", 1)[-1]
        return backend if backend in self.backends else self.overflow


class RuntimeMetrics:
    def __init__(self, guard: CardinalityGuard, registry: CollectorRegistry | None = None, prefix: str = "airt"):
        self.guard = guard
        self.registry = registry or CollectorRegistry()
        r, p = self.registry, prefix
        self.requests = Counter(f"{p}_llm_requests", "LLM requests through the gateway",
                                ["team", "model", "status", "cache"], registry=r)
        self.tokens = Counter(f"{p}_llm_tokens", "Tokens processed", ["team", "model", "direction"], registry=r)
        self.cost = Counter(f"{p}_llm_cost_usd", "Spend in USD (shadow-priced for self-hosted)", ["team", "model"], registry=r)
        self.latency = Histogram(f"{p}_llm_request_duration_seconds", "End-to-end gateway latency",
                                 ["model", "status"], buckets=LATENCY_BUCKETS, registry=r)
        self.ttft = Histogram(f"{p}_llm_time_to_first_token_seconds", "Time to first token (streaming)",
                              ["model"], buckets=TTFT_BUCKETS, registry=r)
        self.prompt_size = Histogram(f"{p}_llm_prompt_tokens", "Prompt size distribution", ["model"],
                                     buckets=TOKEN_BUCKETS, registry=r)
        self.served_by = Counter(f"{p}_llm_served_by", "Requests by serving backend",
                                 ["model", "backend"], registry=r)
        self.guardrail_blocks = Counter(f"{p}_guardrail_blocks", "Requests blocked by guardrails",
                                        ["team", "reason"], registry=r)

    def observe_payload(self, p: dict, cost_usd: float | None = None) -> None:
        """Record one LiteLLM StandardLoggingPayload."""
        md = p.get("metadata") or {}
        team = self.guard.team(md.get("user_api_key_team_alias"))
        model = self.guard.model(p.get("model_group"))
        status = "success" if p.get("status", "success") == "success" else "error"
        cache = "hit" if p.get("cache_hit") else "miss"

        self.requests.labels(team, model, status, cache).inc()
        pt, ct = int(p.get("prompt_tokens") or 0), int(p.get("completion_tokens") or 0)
        self.tokens.labels(team, model, "input").inc(pt)
        self.tokens.labels(team, model, "output").inc(ct)
        self.prompt_size.labels(model).observe(pt)
        cost = p.get("response_cost") if cost_usd is None else cost_usd
        if cost:
            self.cost.labels(team, model).inc(float(cost))

        start, end = p.get("startTime"), p.get("endTime")
        if start and end:
            self.latency.labels(model, status).observe(max(0.0, end - start))
        first = p.get("completionStartTime")
        if p.get("stream") and start and first and first > start:
            self.ttft.labels(model).observe(first - start)

        # Which backend actually served it. During a provider outage this is
        # where you see traffic shift from the primary to the fallback.
        self.served_by.labels(model, self.guard.backend(p.get("model_id"))).inc()

    def observe_block(self, team: str | None, reason: str) -> None:
        self.guardrail_blocks.labels(self.guard.team(team), reason.split(":", 1)[0]).inc()
