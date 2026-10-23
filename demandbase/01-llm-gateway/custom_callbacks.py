"""LiteLLM callback wiring for cost attribution (04) and metrics (05).

Referenced from config.yaml as `custom_callbacks.handler`.
"""

from __future__ import annotations

import os

from fastapi import HTTPException
from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger
from prometheus_client import start_http_server

from costwatch.callback import BatchWriter, event_from_payload
from costwatch.sinks import from_env
from llmobs import CardinalityGuard, RuntimeMetrics


def _csv(name: str, default: str) -> set[str]:
    return {v.strip() for v in os.getenv(name, default).split(",") if v.strip()}


class AiRuntimeLogger(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        guard = CardinalityGuard(
            teams=_csv("AIRT_KNOWN_TEAMS", "account-intel,internal-tools,data-science"),
            models=_csv("AIRT_KNOWN_MODELS", "chat-small,chat-tiny,judge,embed-small"),
            backends=_csv("AIRT_KNOWN_BACKENDS", "primary,secondary"),
        )
        self.metrics = RuntimeMetrics(guard)
        self.costs = BatchWriter(from_env(), batch_size=int(os.getenv("COSTWATCH_BATCH", "50")))
        port = int(os.getenv("AIRT_METRICS_PORT", "9464"))
        try:
            start_http_server(port, registry=self.metrics.registry)
        except OSError:  # another worker in this pod already serves it
            verbose_proxy_logger.info("airt metrics port %s already bound", port)

    async def _record(self, kwargs: dict) -> None:
        payload = kwargs.get("standard_logging_object")
        if not payload:
            return
        event = event_from_payload(payload)
        self.metrics.observe_payload(payload, cost_usd=event.cost_usd)
        await self.costs.add(event)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._record(kwargs)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        await self._record(kwargs)

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict, traceback_str=None):
        if isinstance(original_exception, HTTPException) and isinstance(original_exception.detail, dict):
            if str(original_exception.detail.get("error", "")).startswith("guardrail_blocked"):
                for reason in original_exception.detail.get("reasons", []):
                    self.metrics.observe_block(getattr(user_api_key_dict, "team_alias", None), reason)
        return None


handler = AiRuntimeLogger()
