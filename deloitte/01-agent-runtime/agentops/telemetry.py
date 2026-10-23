"""Metrics, traces and run logs for agent runs.

* Prometheus: outcomes, steps, tool errors, tokens, cost. All labels come from
  closed sets (outcome enum, tool names, error kinds), never from user input.
* OpenTelemetry: one `agent.run` span with a child per step and tool call, so
  a slow or expensive run can be read step by step.
* JSONL run log: one line per run, the input to 03-drift-cost-sentinel and
  to offline analysis. Prompt text is not logged; only sizes and outcomes.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from prometheus_client import CollectorRegistry, Counter, Histogram

STEP_BUCKETS = (1, 2, 3, 4, 5, 6, 8, 10, 15)
RUN_BUCKETS = (0.5, 1, 2, 4, 8, 15, 30, 60, 120)
COST_BUCKETS = (0.00001, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05)


class Telemetry:
    def __init__(self, registry: CollectorRegistry | None = None, tracer: trace.Tracer | None = None,
                 run_log: str | Path | None = None):
        self.registry = registry or CollectorRegistry()
        r = self.registry
        self.tracer = tracer or trace.get_tracer("agentops")
        self.runs = Counter("agent_runs", "Agent runs by outcome", ["agent", "outcome"], registry=r)
        self.steps = Histogram("agent_run_steps", "Model steps per run", ["agent"], buckets=STEP_BUCKETS, registry=r)
        self.duration = Histogram("agent_run_duration_seconds", "Wall-clock time per run", ["agent", "outcome"],
                                  buckets=RUN_BUCKETS, registry=r)
        self.cost = Histogram("agent_run_cost_usd", "Cost per run (shadow-priced for local models)", ["agent"],
                              buckets=COST_BUCKETS, registry=r)
        self.cost_total = Counter("agent_cost_usd", "Total agent spend", ["agent"], registry=r)
        self.tokens = Counter("agent_tokens", "Tokens", ["agent", "direction"], registry=r)
        self.tool_calls = Counter("agent_tool_calls", "Tool calls", ["agent", "tool", "result"], registry=r)
        self.llm_errors = Counter("agent_llm_errors", "Model call failures", ["agent", "retryable"], registry=r)
        self.invalid_outputs = Counter("agent_invalid_outputs", "Model replies that broke the action protocol",
                                       ["agent"], registry=r)
        self.run_log = Path(run_log) if run_log else None
        self._log_lock = threading.Lock()

    @contextmanager
    def span(self, name: str, **attrs):
        with self.tracer.start_as_current_span(name) as s:
            for k, v in attrs.items():
                if v is not None:
                    s.set_attribute(k, v)
            yield s

    def record_run(self, agent: str, result) -> None:
        self.runs.labels(agent, result.outcome).inc()
        self.steps.labels(agent).observe(result.steps)
        self.duration.labels(agent, result.outcome).observe(result.duration_s)
        self.cost.labels(agent).observe(result.cost_usd)
        self.cost_total.labels(agent).inc(result.cost_usd)
        self.tokens.labels(agent, "input").inc(result.prompt_tokens)
        self.tokens.labels(agent, "output").inc(result.completion_tokens)
        if self.run_log:
            line = json.dumps(result.log_record(agent))
            with self._log_lock, self.run_log.open("a") as f:
                f.write(line + "\n")
