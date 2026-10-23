"""The usage event: one row per LLM call, the unit of cost attribution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass
class UsageEvent:
    request_id: str
    team: str
    model: str  # gateway model group, e.g. "chat-small"
    provider_model: str  # what actually served it, e.g. "ollama/qwen2.5:0.5b"
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    feature: str = "unknown"  # product feature tag sent by the caller
    api_key_alias: str = ""
    cache_hit: bool = False
    status: str = "success"
    latency_ms: float = 0.0
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_row(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.strftime("%Y-%m-%d %H:%M:%S.%f")
        d["total_tokens"] = self.total_tokens
        return d
