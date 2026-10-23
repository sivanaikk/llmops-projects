"""Model clients. Anything OpenAI-compatible works: Ollama (`/v1`), a LiteLLM
gateway (see demandbase/01-llm-gateway), Azure OpenAI behind a gateway, or
AWS Bedrock via LiteLLM."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


class LLMError(Exception):
    def __init__(self, msg: str, retryable: bool):
        self.retryable = retryable
        super().__init__(msg)


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[dict], timeout: float, max_tokens: int) -> LLMResult: ...


class OpenAICompatClient:
    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("AGENT_MODEL", "qwen2.5:1.5b")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        self.http = httpx.Client()

    def complete(self, messages: list[dict], timeout: float, max_tokens: int) -> LLMResult:
        t0 = time.perf_counter()
        try:
            r = self.http.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    # Small models follow a JSON protocol far more reliably with JSON mode on.
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
        except httpx.TimeoutException as e:
            raise LLMError(f"llm timeout after {timeout:.1f}s", retryable=True) from e
        except httpx.TransportError as e:
            raise LLMError(f"llm transport error: {e}", retryable=True) from e
        if r.status_code == 429 or r.status_code >= 500:
            raise LLMError(f"llm {r.status_code}: {r.text[:200]}", retryable=True)
        if r.status_code >= 400:
            raise LLMError(f"llm {r.status_code}: {r.text[:200]}", retryable=False)
        body = r.json()
        usage = body.get("usage") or {}
        return LLMResult(
            text=body["choices"][0]["message"]["content"] or "",
            model=body.get("model", self.model),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_s=time.perf_counter() - t0,
        )


class ScriptedLLM:
    """Deterministic stand-in for tests, evals of the harness itself, and chaos drills.

    `script` is a list of replies (str, or Exception to raise), or a callable
    taking the message list and returning a reply.
    """

    def __init__(self, script: list | Callable[[list[dict]], str], model: str = "scripted", tokens_per_char: float = 0.25):
        self.script = script
        self.model = model
        self.calls: list[list[dict]] = []
        self._i = 0
        self.tpc = tokens_per_char

    def complete(self, messages: list[dict], timeout: float, max_tokens: int) -> LLMResult:
        self.calls.append([dict(m) for m in messages])
        if callable(self.script):
            reply = self.script(messages)
        else:
            reply = self.script[min(self._i, len(self.script) - 1)]
            self._i += 1
        if isinstance(reply, BaseException):
            raise reply
        prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return LLMResult(reply, self.model, int(prompt_chars * self.tpc), int(len(reply) * self.tpc), 0.0)
