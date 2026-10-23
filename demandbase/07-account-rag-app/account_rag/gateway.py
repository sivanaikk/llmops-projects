"""Thin client for the LiteLLM gateway (OpenAI-compatible).

Every call carries:
* the team's virtual key  -> spend/limits/guardrail policy are per team
* `metadata.feature` tag   -> cost attribution per product feature
* W3C `traceparent`        -> the gateway span joins the app's trace
"""

from __future__ import annotations

import os
from typing import Protocol

import httpx

try:
    from llmobs import inject_headers
except ImportError:  # tracing optional
    def inject_headers(h=None):
        return dict(h or {})


class ChatClient(Protocol):
    def chat(self, model: str, messages: list[dict], feature: str, **params) -> dict: ...

    def embed(self, model: str, text: str, feature: str) -> list[float]: ...


class GatewayError(RuntimeError):
    def __init__(self, status: int, body: str):
        self.status = status
        super().__init__(f"gateway returned {status}: {body[:300]}")


class GatewayClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 120):
        self.base_url = (base_url or os.getenv("GATEWAY_URL", "http://localhost:4000")).rstrip("/")
        self.api_key = api_key or os.getenv("GATEWAY_API_KEY") or os.getenv("LITELLM_MASTER_KEY", "sk-local-master")
        self.http = httpx.Client(base_url=self.base_url, timeout=timeout)

    def _post(self, path: str, body: dict) -> dict:
        headers = inject_headers({"Authorization": f"Bearer {self.api_key}"})
        r = self.http.post(path, json=body, headers=headers)
        if r.status_code >= 400:
            raise GatewayError(r.status_code, r.text)
        return r.json()

    def chat(self, model: str, messages: list[dict], feature: str, **params) -> dict:
        body = {"model": model, "messages": messages, "metadata": {"feature": feature}, "tags": [f"feature:{feature}"], **params}
        return self._post("/v1/chat/completions", body)

    def embed(self, model: str, text: str, feature: str) -> list[float]:
        body = {"model": model, "input": text, "metadata": {"feature": feature}}
        return self._post("/v1/embeddings", body)["data"][0]["embedding"]
