# Learn: observability for LLM traffic

**You'll be able to:** choose what goes in metrics vs traces vs logs; keep metric
cardinality bounded; instrument LLM latency (including TTFT) and cost; capture
prompts in traces safely; write burn-rate alerts and unit-test them.
**Time:** ~2 h · **Needs:** Python (promtool for the alert tests)

---

## 1. The problem

LLM traffic breaks the usual dashboards. Requests take seconds to minutes, cost
varies 100× between calls, and the most useful debugging data (the prompt) is also
the most sensitive. Instrument naively and you either can't debug, or you leak PII
into your trace backend and blow up your metrics bill.

## 2. Concepts

**Metrics vs traces vs logs:**

| | Use for | Cardinality |
|---|---|---|
| metrics | rates, SLOs, alerts, dashboards (team, model, status) | **must be bounded** |
| traces | one request end to end: retrieval → gateway → provider; prompt capture | unbounded is fine |
| logs | events, errors, audit | unbounded, but cost per byte |

**Cardinality.** Every distinct label combination is a separate time series. A
`user_id` label turns 10 series into millions. [`llmobs/metrics.py`](llmobs/metrics.py) `CardinalityGuard`
allowlists label values and maps anything else to `other`.

**LLM-shaped histograms:** latency buckets up to 60s (default web buckets stop at 10s);
TTFT for streaming; prompt-size buckets to spot context stuffing.

**Prompt capture in traces** ([`llmobs/tracing.py`](llmobs/tracing.py)): **sampled** (10%),
**redacted** (same guardkit rules as the gateway), **truncated**.

**Alerts are code, so test them.** [`prometheus/rules/slo-alerts.test.yml`](prometheus/rules/slo-alerts.test.yml)
feeds synthetic series to promtool and asserts each alert fires or stays quiet. Those tests caught a real
bug in this lab: a routing label `team: ai-runtime` overwrote the metric's own `team` label, so a
guardrail storm for *account-intel* would have arrived labelled *ai-runtime*.

## 3. Walkthrough

```bash
pytest 05-llm-observability -q
promtool check rules 05-llm-observability/prometheus/rules/slo-alerts.yml
promtool test rules 05-llm-observability/prometheus/rules/slo-alerts.test.yml   # SUCCESS
```

Read `test_cardinality_guard_collapses_unknown_labels` in [`tests/test_llmobs.py`](tests/test_llmobs.py):
50 random teams and models produce **one** series. Then open the dashboard JSON
[`grafana/dashboards/ai-runtime.json`](grafana/dashboards/ai-runtime.json) and find the panel for each alert.
With the stack running: Grafana at localhost:3000, traces at localhost:16686.

## 4. Exercises

```bash
make check EX=06     # cardinality guard + series counting
make check EX=03     # burn-rate arithmetic used by the SLO alerts
```

Challenges:
1. Add a promtool test proving `LLMGatewayErrorBudgetSlowBurn` fires at 4% errors over 6h but not at 2%.
2. Add a `feature` label to the cost counter. Is it safe? (How many features exist, and who controls the values?)
3. Configure tail-based sampling in an OTel collector so 100% of *error* traces are kept but only 10% of successes.

## 5. Break it

```bash
make break-it ID=metrics-unbounded-team-label
make break-it ID=traces-capture-raw-pii
make break-it ID=alert-routing-label-clobbers-team     # the real bug; needs promtool
```

## 6. Check yourself

<details><summary>1. Where do you put the request ID: metric label, trace attribute or log field?</summary>

Trace attribute (and logs). As a metric label it creates one series per request.
</details>

<details><summary>2. p95 latency is fine but users complain the chat feels slow. What's missing?</summary>

TTFT. A streaming response can take 8s overall and still feel fast if the first token arrives in 300ms, or
feel broken if nothing appears for 5s. Measure both.
</details>

<details><summary>3. Why sample prompt capture instead of capturing 100% redacted?</summary>

Redaction isn't perfect (names, addresses), so capturing everything multiplies the risk and the storage
cost for little extra debugging value. 10% of traces is plenty to see patterns.
</details>

## 7. In the interview

* "What did you instrument for LLM features?" Requests by status and cache, latency/TTFT histograms,
  tokens and cost by team, served-by backend, guardrail blocks: all with bounded labels.
* "Tell me about chasing cardinality or cost in a metrics backend." The guard, and why IDs go in traces.
* "How do you know your alerts work?" promtool unit tests, plus the routing-label bug they caught.

## Go further
* OpenTelemetry GenAI semantic conventions
* Prometheus docs: "Instrumentation: use labels with care"; promtool unit testing
