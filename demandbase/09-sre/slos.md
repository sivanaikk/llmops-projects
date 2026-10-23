# SLOs: AI Runtime (LLM gateway)

The gateway is the single front door to every model. If it's down, every AI
feature is down, so its SLOs are stricter than any single provider's.

| SLI | Definition (PromQL source: `airt_*` metrics) | SLO (28d) | Error budget |
|---|---|---|---|
| **Availability** | `status="error"` / all requests. Errors = provider failures that survived retries + fallbacks, gateway 5xx. **Excludes** 4xx the caller caused: guardrail blocks, budget/rate-limit 429s, bad requests. | 99.5% | 0.5%, about 3.4 h of full outage |
| **Latency** (chat-small, non-streaming) | share of successful requests completing in < 8 s (`le="8.0"` bucket) | 95% | 5% slow |
| **TTFT** (streaming) | p95 time-to-first-token | < 2 s | tracked, not alerted yet |
| **Cost attribution coverage** | share of spend rows with a known team (`team != "unattributed"`) | 99% | showback is only useful if it's complete |

Why these numbers: the models are small and run on CPU in the lab, so the
latency target is generous. In production with hosted providers the latency
SLO would be per model group and tighter (e.g. p95 < 4 s for the default chat model).

## Alerting policy

Burn-rate alerts, multiwindow (Google SRE workbook ch. 5):

| Alert | Condition | Action |
|---|---|---|
| `LLMGatewayErrorBudgetFastBurn` | 1h **and** 5m error ratio > 14.4 x 0.5% | **page** |
| `LLMGatewayErrorBudgetSlowBurn` | 6h **and** 30m error ratio > 6 x 0.5% | ticket |
| `LLMGatewayDown` | metrics target down 2m | **page** |
| `LLMGatewayLatencySLO` | >5% of chat-small slower than 8s for 15m | ticket |
| `LLMPrimaryProviderDegraded` | >50% chat-small served by secondary for 10m | ticket (users are fine; resilience is reduced) |
| `LLMDegradedModelServing` | chat-small failing and chat-tiny serving | ticket + notify feature owners (quality is degraded) |
| `LLMSpendSpike` | team's hourly spend > 3x its 7-day baseline for 30m | ticket to owning team + #ai-runtime |
| `GuardrailBlockSpike` | > 5 blocks/min per team+reason for 10m | ticket (attack or a bad policy rollout) |

Alerts carry `owner: ai-runtime` for routing; the metric's own `team` label
(the *consuming* team) is preserved so per-team alerts say who is affected.
All alerts are unit-tested: `promtool test rules 05-llm-observability/prometheus/rules/slo-alerts.test.yml`.

## Error budget policy

* Budget > 50%: ship freely.
* Budget 0-50%: gateway changes need a second reviewer and a game-day-tested rollback.
* Budget exhausted: freeze non-reliability gateway changes until the 28d window recovers; the postmortem action items get priority.
