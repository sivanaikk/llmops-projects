# Runbook: SLO burn (SLOFastBurn / SLOSlowBurn / SLOBudgetLeak)

1. **Which outcomes are burning?** Grafana → Agent Runtime → "Runs by outcome".
   - `llm_unavailable`: the model path. Go to [llm-provider-degraded.md](llm-provider-degraded.md).
   - `deadline`: slow model or tools. Check run p95, tool latency, model latency.
   - `invalid_output`: the model is breaking the protocol, almost always a model or prompt change.
2. **What changed?** Argo CD history for `agent-runtime-prod`, gateway config history, model version.
   Roll back first: `budgetgate` always admits `--change-type rollback`.
3. Fast burn = page = incident: follow [incident-response.md](../incident-response.md).
4. Slow burn / leak: open a ticket and find the cause within the week before the budget runs out.
