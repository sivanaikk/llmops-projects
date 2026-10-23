# Runbook: drift or cost anomaly (AIDriftOrCostAnomaly)

`03-drift-cost-sentinel` flagged a critical shift. Read the report (CronJob logs
or `python -m sentinel.monitor --runs runs.jsonl`); the `signal` label says which.

| Signal | Likely cause | Action |
|---|---|---|
| `question_chars` / input drift | users now paste logs, a new client integration | check evals still represent real inputs; add tasks; maybe raise token budget |
| `prompt_tokens` without input drift | **we** changed something: retrieval, system prompt, tool output size | find the change; cost goes up with it |
| `outcome`, `invalid_output_rate`, `steps` | model or prompt regression | roll back; run evals |
| `model` | traffic moved to a different model (fallback serving, config change) | check the gateway fallbacks |
| `tool_error_rate`, `tools` | a tool dependency failing | see [tool-dependency-down.md](tool-dependency-down.md) |
| `cost_per_run`, `hourly_spend` | prompt bloat, loops, pricier model | see [agent-runaway.md](agent-runaway.md) |

Drift is not automatically bad: a new use case might be good news. The action
is to make sure evals and budgets reflect the new reality.
