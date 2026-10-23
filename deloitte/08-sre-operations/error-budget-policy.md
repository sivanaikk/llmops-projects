# Error budget policy

Agreed between the product owner and SRE for each tier-1 service. Enforced by
`budgetgate` in CI and as an Argo CD PreSync hook, so the policy doesn't depend
on anyone remembering it.

| Budget remaining (28d) | Releases | Who decides |
|---|---|---|
| > 10% and burn rates within policy | Ship freely | Team |
| 0-10%, or 1h burn > 14.4x, or 6h burn > 6x | **Blocked**, except reliability fixes with an approved `CHG-`/`INC-` ticket | Service owner + SRE approve the ticket |
| < 0% (exhausted) | Feature freeze until the budget recovers; postmortem action items take priority | Engineering manager + SRE |

**Always allowed:** rollbacks (`--change-type rollback`). Blocking the way out of an incident makes it worse.

**If the gate can't reach Prometheus:** tier-1 services fail **closed** (no SLO
data, no release). Tier-3 services may choose fail-open in their spec.

**Overrides are audited:** the ticket ID is recorded in the gate's JSON output,
which CI keeps as a job log and Argo CD keeps in the hook Job's history.

## Reviewing the policy

Quarterly, with the product team: was the SLO too tight (paged with no user
impact) or too loose (users complained while we were "in budget")? Adjust the
objective in the spec. The rules and the gate follow automatically.
