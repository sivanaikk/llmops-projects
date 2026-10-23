# 04 · Cost control and showback (`costwatch`)

> JD: *"Per-team and per-model attribution, budgets, quotas. LLM spend is the
> kind of line item that quietly triples; your job is to make it legible and
> then make it smaller."*

```
gateway callback ──► UsageEvent (team, feature, model, provider, tokens, cost, cache_hit, latency)
                 ──► BatchWriter (async, batched, dead-letter on sink failure)
                 ──► ClickHouse llmops.llm_usage  ──► daily rollup MV ──► Grafana / showback
```

| Piece | File |
|---|---|
| Attribution: team from the virtual key, **feature** from request metadata/tags, model group and the deployment that actually served it | [`costwatch/callback.py`](costwatch/callback.py) |
| Shadow pricing for self-hosted models (otherwise $0) | [`costwatch/pricing.py`](costwatch/pricing.py) |
| ClickHouse schema: MergeTree partitioned by month, 13-month TTL, `SummingMergeTree` daily rollup kept forever | [`sql/clickhouse_schema.sql`](sql/clickhouse_schema.sql) |
| Budgets + **burn-rate forecasting** (projects month-end spend from the current run rate) | [`costwatch/budgets.py`](costwatch/budgets.py), [`budgets.yaml`](budgets.yaml) |
| Showback report: by team, team×model, top features, cache savings, budget alerts | [`costwatch/report.py`](costwatch/report.py) |

Two layers of budget:

| | Where | Effect |
|---|---|---|
| **Hard** | LiteLLM team/key `max_budget` ([teams.yaml](../01-llm-gateway/teams.yaml)) | requests rejected once exhausted (backstop) |
| **Soft** | `budgets.yaml` + `costwatch.report` + `LLMSpendSpike` alert | warning when the *projected* month-end spend exceeds budget, days before the hard limit |

Cache hits are logged at what they *would* have cost and excluded from
billable spend, so "saved by caching" is directly comparable to spend.

```bash
make showback DEMO=1     # synthetic traffic in DuckDB
make showback            # against COSTWATCH_SINK=clickhouse when the stack is up
```
