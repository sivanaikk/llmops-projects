# Runbook: agent runaway (budget stops, invalid output, spend over budget)

**Alerts:** `AgentBudgetStopsHigh`, `AgentInvalidOutputRateHigh`, `AgentSpendOverDailyBudget`

1. Did the model or prompt change? Compare `model` in the run log and the last deploy.
   Run the eval suite on the current config: `python -m agentevals run variants/baseline.yaml`.
2. Look at a few runs: Jaeger, service `agent-runtime`, sort by duration. Repeating tool
   calls = loop; many short steps with corrections = protocol breakage.
3. Mitigate:
   - roll back the model/prompt change, or
   - lower `AGENT_MAX_STEPS` / `AGENT_MAX_COST_USD` (Helm values → Argo CD) to cap damage, or
   - cut the team's gateway budget/rpm for an immediate spend stop.
4. Add the failing pattern as an eval task so it can't regress silently again.
