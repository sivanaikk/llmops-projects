import random

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llmobs import CardinalityGuard, LLMTracer, RuntimeMetrics


def guard():
    return CardinalityGuard(
        teams={"account-intel", "internal-tools"},
        models={"chat-small", "chat-tiny"},
        backends={"primary", "secondary"},
    )


def payload(**over):
    p = {
        "model_group": "chat-small",
        "status": "success",
        "prompt_tokens": 300,
        "completion_tokens": 50,
        "response_cost": 0.001,
        "startTime": 10.0,
        "endTime": 10.8,
        "completionStartTime": 10.2,
        "stream": True,
        "model_id": "chat-small-primary",
        "metadata": {"user_api_key_team_alias": "account-intel"},
    }
    p.update(over)
    return p


def val(m, name, labels):
    return m.registry.get_sample_value(name, labels)


def test_metrics_from_payload():
    m = RuntimeMetrics(guard())
    m.observe_payload(payload())
    lbl = {"team": "account-intel", "model": "chat-small"}
    assert val(m, "airt_llm_requests_total", {**lbl, "status": "success", "cache": "miss"}) == 1
    assert val(m, "airt_llm_tokens_total", {**lbl, "direction": "input"}) == 300
    assert val(m, "airt_llm_cost_usd_total", lbl) == 0.001
    assert val(m, "airt_llm_time_to_first_token_seconds_count", {"model": "chat-small"}) == 1
    assert val(m, "airt_llm_served_by_total", {"model": "chat-small", "backend": "primary"}) == 1


def test_cardinality_guard_collapses_unknown_labels():
    m = RuntimeMetrics(guard())
    for i in range(50):
        m.observe_payload(payload(model_group=f"user-model-{i}", model_id=f"deploy-{i}",
                                  metadata={"user_api_key_team_alias": f"team-{i}"}))
    series = {
        tuple(sorted(s.labels.items()))
        for metric in m.registry.collect() if metric.name == "airt_llm_requests"
        for s in metric.samples if s.name.endswith("_total")
    }
    assert len(series) == 1  # all collapsed to team=other, model=other


def test_guardrail_block_reason_is_bounded():
    m = RuntimeMetrics(guard())
    m.observe_block("account-intel", "pii_blocked:US_SSN,CREDIT_CARD")
    assert val(m, "airt_guardrail_blocks_total", {"team": "account-intel", "reason": "pii_blocked"}) == 1


def make_tracer(ratio):
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    return LLMTracer(provider.get_tracer("t"), capture_ratio=ratio, rng=random.Random(0)), exp


def test_llm_span_redacts_captured_content():
    t, exp = make_tracer(1.0)
    with t.llm_call("chat", "chat-small", feature="account-summary", team="account-intel") as s:
        s.record_prompt([{"role": "user", "content": "email bob@acme.com"}])
        s.record_response({"model": "qwen2.5:0.5b", "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                           "choices": [{"finish_reason": "stop", "message": {"content": "call 415-555-0134"}}]})
    (span,) = exp.get_finished_spans()
    assert "bob@acme.com" not in span.attributes["gen_ai.prompt"]
    assert "415-555-0134" not in span.attributes["gen_ai.completion"]
    assert span.attributes["gen_ai.usage.input_tokens"] == 5


def test_llm_span_skips_content_when_not_sampled():
    t, exp = make_tracer(0.0)
    with t.llm_call("chat", "chat-small", feature="f", team="t") as s:
        s.record_prompt([{"role": "user", "content": "hi"}])
    (span,) = exp.get_finished_spans()
    assert "gen_ai.prompt" not in span.attributes
    assert span.attributes["llmobs.content_captured"] is False
