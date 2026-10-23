# Production readiness review (PRR): AI and agentic workloads

Co-defined with the product team before a service gets production traffic.
A "no" doesn't block launch on its own: each one is an explicit, owned risk.

## Reliability
- [ ] SLO spec merged in `02-error-budget-gate/slos/`, objective agreed with the product owner
- [ ] Every agent outcome classified as SLO-error or not (see [slo-catalogue.md](slo-catalogue.md))
- [ ] Load test at 2x expected peak passes the k6 thresholds; capacity plan recorded (`resilience.capacity`)
- [ ] Chaos experiments pass: model latency, model outage (fail fast), stall (deadline holds), flaky resets
- [ ] Run deadline, step, token and cost budgets set; fallback answers reviewed with product
- [ ] HPA, PDB, zone spread, graceful shutdown longer than the run deadline
- [ ] Rollback tested; a rollback doesn't need the gate

## AI-specific
- [ ] Eval suite exists with trajectory checks, safety and robustness tasks, k ≥ 2 trials
- [ ] Baseline eval results logged in MLflow; promotion gate thresholds agreed
- [ ] Drift baseline captured (`03-drift-cost-sentinel`); owner for drift tickets named
- [ ] Model access goes through the LLM gateway (quotas, fallbacks, guardrails, cost attribution)
- [ ] Tools are least-privilege: read-only by default; side-effecting tools are not retried and need confirmation
- [ ] Prompt/response logging decision recorded: what is captured, redacted, sampled, retained
- [ ] Cost budget per run and per day agreed; anomaly alert routed to the owning team

## Operability
- [ ] Dashboards: SLO/budget, outcomes, steps, tools, cost ([agent-runtime.json](../observability/grafana/dashboards/agent-runtime.json))
- [ ] Every alert has a runbook, and the alert has a promtool unit test
- [ ] On-call rotation includes someone who knows the product domain
- [ ] Traces join app → gateway → model (OpenTelemetry)

## Security and governance
- [ ] Secrets in Key Vault, workload identity: no keys in pods or pipelines
- [ ] NetworkPolicy: agent egress allowlisted
- [ ] Segregation of duties: prod sync and gate overrides need someone other than the author
- [ ] Data governance sign-off for any customer data in prompts, logs or eval sets
