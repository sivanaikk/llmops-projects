"""Turn LiteLLM `standard_logging_object` payloads into UsageEvents and ship them.

The batching writer keeps the hot path cheap: the gateway callback only
appends to a buffer; a flush happens every `batch_size` events or
`flush_seconds`, off the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .events import UsageEvent
from .pricing import price
from .sinks import JsonlSink, Sink

log = logging.getLogger("costwatch")


def event_from_payload(p: dict) -> UsageEvent:
    md = p.get("metadata") or {}
    requester = md.get("requester_metadata") or {}
    model_group = p.get("model_group") or p.get("model") or "unknown"
    pt, ct = int(p.get("prompt_tokens") or 0), int(p.get("completion_tokens") or 0)

    cost = float(p.get("response_cost") or 0.0)
    if cost == 0.0:
        # Self-hosted models come back as $0; fall back to the shadow price so
        # showback still reflects usage.
        cost = price(model_group, pt, ct)

    start, end = p.get("startTime") or 0.0, p.get("endTime") or 0.0
    return UsageEvent(
        request_id=p.get("id") or "",
        team=md.get("user_api_key_team_alias") or md.get("team_alias") or "unattributed",
        model=model_group,
        provider_model=f"{p.get('custom_llm_provider') or ''}/{p.get('model') or ''}".strip("/"),
        prompt_tokens=pt,
        completion_tokens=ct,
        cost_usd=cost,
        feature=str(requester.get("feature") or _tag(p.get("request_tags"), "feature") or "unknown"),
        api_key_alias=md.get("user_api_key_alias") or "",
        cache_hit=bool(p.get("cache_hit")),
        status=p.get("status") or "success",
        latency_ms=max(0.0, (end - start) * 1000),
    )


def _tag(tags: list | None, key: str) -> str | None:
    for t in tags or []:
        if isinstance(t, str) and t.startswith(f"{key}:"):
            return t.split(":", 1)[1]
    return None


class BatchWriter:
    def __init__(self, sink: Sink, batch_size: int = 50, flush_seconds: float = 5.0, dead_letter: Sink | None = None):
        self.sink = sink
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self.dead_letter = dead_letter or JsonlSink("/tmp/costwatch-deadletter.jsonl")
        self._buf: list[UsageEvent] = []
        self._last_flush = time.monotonic()
        self._lock = asyncio.Lock()

    async def add(self, event: UsageEvent) -> None:
        self._buf.append(event)
        if len(self._buf) >= self.batch_size or time.monotonic() - self._last_flush >= self.flush_seconds:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            batch, self._buf = self._buf, []
            self._last_flush = time.monotonic()
            if not batch:
                return
            try:
                await asyncio.to_thread(self.sink.write, batch)
            except Exception:  # never fail a user request because billing is down
                log.exception("costwatch sink write failed; %d events to dead letter", len(batch))
                await asyncio.to_thread(self.dead_letter.write, batch)
