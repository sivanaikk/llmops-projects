# 05 · LLM observability (`llmobs`)

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"Traces, spans, prompt/response capture, ingest and billing visibility
> for every AI feature"* and *"you've instrumented systems, chased
> cardinality and cost in a metrics/logging backend, and built alerts that
> fire when they should."*

## Metrics ([`llmobs/metrics.py`](llmobs/metrics.py))

| Metric | Labels | Why |
|---|---|---|
| `airt_llm_requests_total` | team, model, status, cache | availability SLI, cache hit ratio |
| `airt_llm_request_duration_seconds` | model, status | latency SLI (LLM-sized buckets up to 60s) |
| `airt_llm_time_to_first_token_seconds` | model | streaming UX |
| `airt_llm_tokens_total` | team, model, direction | throughput, prompt-bloat detection |
| `airt_llm_cost_usd_total` | team, model | spend rate → `LLMSpendSpike` |
| `airt_llm_served_by_total` | model, backend | failover visibility |
| `airt_guardrail_blocks_total` | team, reason | attack or bad-policy detection |

**Cardinality control** is built in: `team`, `model` and `backend` are checked
against allowlists, and unknown values collapse to `other`. User IDs, key IDs
and prompts are never labels. A test pushes 50 random teams/models through
and asserts they produce exactly one series.

## Traces ([`llmobs/tracing.py`](llmobs/tracing.py))

OpenTelemetry spans using the GenAI semantic conventions
(`gen_ai.request.model`, `gen_ai.usage.input_tokens`, ...). The app sends a W3C
`traceparent` to the gateway, and LiteLLM's `otel` callback continues it, so
one trace shows *retrieve → gateway → provider*.

Prompt/response capture is **sampled** (`LLMOBS_CAPTURE_RATIO`, default 10%),
**PII-redacted** with the same guardkit rules as the gateway, and **truncated**.
Full capture of every prompt multiplies storage cost and data risk for little
extra debugging value.

## Alerts ([`prometheus/rules/slo-alerts.yml`](prometheus/rules/slo-alerts.yml))

Multiwindow burn-rate SLO alerts, latency SLO, provider-degraded, degraded-model
serving, spend spike and guardrail spike, each linked to a runbook in
[09-sre](../09-sre/). **Alerts have unit tests**
([`slo-alerts.test.yml`](prometheus/rules/slo-alerts.test.yml)):

```bash
promtool test rules 05-llm-observability/prometheus/rules/slo-alerts.test.yml
```

## Dashboards and logs

* [`grafana/dashboards/ai-runtime.json`](grafana/dashboards/ai-runtime.json): SLO stats, error ratio vs budget, latency/TTFT, served-by backend, spend by team, tokens, cache hit ratio, prompt size, and a ClickHouse month-to-date showback table.
* Loki via promtail ([`loki/promtail.yml`](loki/promtail.yml)) keeps only runtime services and **scrubs `sk-` keys** before shipping.
* **Datadog** (the JD's production stack): set `success_callback: ["datadog_llm_observability"]` in the gateway config plus `DD_API_KEY`. The Prometheus/OTel setup here is the vendor-neutral equivalent.
