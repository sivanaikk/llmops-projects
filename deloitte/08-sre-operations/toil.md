# Toil inventory

Toil = manual, repetitive, automatable work that scales with the service.
Target: under 50% of SRE time; tracked monthly from the on-call log.

| Task | Frequency | Est. time/month | Status |
|---|---|---|---|
| Deciding whether a release may ship given recent incidents | every prod deploy | 4h | **Automated**: `budgetgate` in CI + Argo CD PreSync |
| Writing Prometheus rules for each new SLO | per service | 2h | **Automated**: `budgetgate rules` from the spec |
| Checking whether a model/prompt change made answers worse | per change | 6h | **Automated**: `agentevals` gate in CI + nightly |
| Spotting cost spikes from the invoice | monthly | 3h | **Automated**: sentinel + `AgentSpendOverDailyBudget` |
| Restarting agents stuck on a dead dependency | weekly | 2h | **Eliminated**: circuit breakers + run deadline |
| Re-running chaos drills by hand | quarterly | 4h | Partly automated: `resilience.chaos`; cloud runs still started by hand |
| Rotating provider API keys | quarterly | 1h | Planned: workload identity removes keys entirely |
