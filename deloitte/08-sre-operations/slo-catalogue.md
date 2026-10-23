# SLO catalogue

SLOs live as code in [`02-error-budget-gate/slos/`](../02-error-budget-gate/slos/).
`budgetgate rules` turns them into Prometheus recording rules and burn-rate
alerts, and `budgetgate check` uses the same specs to admit or block releases.
One definition drives the dashboard, the pages and the deploy gate.

| Service | SLI | SLO | Window | Owner |
|---|---|---|---|---|
| agent-runtime | runs **not** ending in `llm_unavailable`, `deadline` or `invalid_output` | 99% | 28d | team-ai-platform + SRE |
| llm-gateway | gateway requests not failing after retries and fallbacks | 99.5% | 28d | team-ai-platform |

## Why the agent SLI looks like this

An agent run has more outcomes than "200 or 500". We classified each one before writing the SLO:

| Outcome | Counts against the SLO? | Why |
|---|---|---|
| `success` | no | |
| `llm_unavailable`, `deadline`, `invalid_output` | **yes** | the platform failed the user |
| `budget_steps`, `budget_cost`, `budget_tokens`, `loop_detected` | no | the guardrail did its job; tracked by `AgentBudgetStopsHigh` instead |

Counting budget stops as errors would page SRE for a prompt problem and push
teams to raise the limits, which is the wrong fix. Ignoring them entirely would
hide a struggling agent. So they get their own ticket-level alert.

## What an SLO doesn't catch (and what does)

| Failure mode | Caught by |
|---|---|
| Answers silently getting worse | nightly agent evals (`04-agent-evals`) + `AgentInvalidOutputRateHigh` |
| Users asking different things than we tested | input drift in `03-drift-cost-sentinel` |
| Spend quietly tripling | `AgentSpendOverDailyBudget` + sentinel cost anomalies |
| A tool dependency down but the agent "working around" it | `AgentToolCircuitOpen` |
