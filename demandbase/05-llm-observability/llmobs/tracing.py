"""OpenTelemetry tracing for LLM features, using the GenAI semantic conventions.

Prompt/response capture is the most useful and the most dangerous part of LLM
observability. Here it is:

* **opt-in and sampled** (`capture_ratio`): full content on a fraction of
  traces is enough to debug; 100% capture multiplies storage cost and risk,
* **redacted** with the same guardkit PII rules the gateway enforces,
* **truncated** so one 100k-token prompt can't blow up a span exporter.

Spans from the app carry a W3C `traceparent` to the gateway (see
`inject_headers`), and LiteLLM's built-in `otel` callback continues the trace,
so one trace shows retrieval -> gateway -> provider.
"""

from __future__ import annotations

import os
import random
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

MAX_CONTENT_CHARS = 4000


def _default_redactor() -> Callable[[str], str]:
    try:
        from guardkit.pii import redact

        return lambda s: redact(s).text
    except ImportError:  # observability must not hard-depend on guardrails
        return lambda s: s


def setup_tracing(service_name: str, exporter: SpanExporter | None = None, batch: bool = True) -> TracerProvider:
    """Configure a global tracer provider. With no exporter, use OTLP/HTTP if configured."""
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter is None and os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


class LLMTracer:
    def __init__(
        self,
        tracer: trace.Tracer | None = None,
        capture_ratio: float = float(os.getenv("LLMOBS_CAPTURE_RATIO", "0.1")),
        redactor: Callable[[str], str] | None = None,
        rng: random.Random | None = None,
    ):
        self.tracer = tracer or trace.get_tracer("llmobs")
        self.capture_ratio = capture_ratio
        self.redact = redactor or _default_redactor()
        self.rng = rng or random.Random()

    def _content(self, text: str) -> str:
        text = self.redact(text)
        return text if len(text) <= MAX_CONTENT_CHARS else text[:MAX_CONTENT_CHARS] + f"...[+{len(text) - MAX_CONTENT_CHARS} chars]"

    @contextmanager
    def llm_call(self, operation: str, model: str, feature: str, team: str, **attrs: Any) -> Iterator[LLMSpan]:
        with self.tracer.start_as_current_span(f"{operation} {model}", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute("gen_ai.operation.name", operation)
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.system", "litellm")
            span.set_attribute("app.feature", feature)
            span.set_attribute("app.team", team)
            for k, v in attrs.items():
                span.set_attribute(k, v)
            capture = self.rng.random() < self.capture_ratio
            span.set_attribute("llmobs.content_captured", capture)
            yield LLMSpan(span, self, capture)

    @contextmanager
    def step(self, name: str, **attrs: Any) -> Iterator[trace.Span]:
        """Non-LLM pipeline step (retrieval, rerank, post-processing)."""
        with self.tracer.start_as_current_span(name) as span:
            for k, v in attrs.items():
                span.set_attribute(k, v)
            yield span


class LLMSpan:
    def __init__(self, span: trace.Span, owner: LLMTracer, capture: bool):
        self.span, self.owner, self.capture = span, owner, capture

    def record_prompt(self, messages: list[dict]) -> None:
        if self.capture:
            joined = "\n".join(f"[{m.get('role')}] {m.get('content')}" for m in messages)
            self.span.set_attribute("gen_ai.prompt", self.owner._content(joined))

    def record_response(self, response: dict) -> None:
        usage = response.get("usage") or {}
        self.span.set_attribute("gen_ai.response.model", response.get("model", ""))
        self.span.set_attribute("gen_ai.usage.input_tokens", int(usage.get("prompt_tokens") or 0))
        self.span.set_attribute("gen_ai.usage.output_tokens", int(usage.get("completion_tokens") or 0))
        choices = response.get("choices") or [{}]
        self.span.set_attribute("gen_ai.response.finish_reasons", [str(c.get("finish_reason")) for c in choices])
        if self.capture:
            text = (choices[0].get("message") or {}).get("content") or ""
            self.span.set_attribute("gen_ai.completion", self.owner._content(text))


def inject_headers(headers: dict | None = None) -> dict:
    """Add W3C traceparent for the current span so the gateway joins the trace."""
    headers = dict(headers or {})
    inject(headers)
    return headers
