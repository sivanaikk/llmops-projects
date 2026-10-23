# 08 · SRE operations

> JD: *"Operate products and platforms to meet SLOs and error budgets, track
> incident trends and toil"*, *"co-define SLOs and readiness with product
> teams"*, *"write runbooks, technical specs, and blameless postmortems"*.

| Doc | |
|---|---|
| [slo-catalogue.md](slo-catalogue.md) | SLIs/SLOs and how agent outcomes map to SLO errors |
| [error-budget-policy.md](error-budget-policy.md) | What happens at each budget level; enforced by `budgetgate` |
| [production-readiness.md](production-readiness.md) | PRR checklist with AI-specific items (evals, drift baseline, tool permissions, prompt logging) |
| [incident-response.md](incident-response.md) | Severities, incident-command roles, first moves for AI incidents |
| [toil.md](toil.md) | Toil inventory and what each project in this lab automated away |
| [runbooks/](runbooks/) | One per alert: SLO burn, agent runaway, tool down, provider degraded, drift/cost anomaly |
| [postmortems/TEMPLATE.md](postmortems/TEMPLATE.md) | Blameless template with an AI-specific root-cause prompt |

Every `runbook_url` in [`observability/prometheus/rules/`](../observability/prometheus/rules/) points at a file here; CI keeps it that way (see the link check in the repo tests).
