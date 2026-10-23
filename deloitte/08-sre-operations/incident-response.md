# Incident response

## Severity
| Sev | Definition | Response |
|---|---|---|
| SEV1 | Tier-1 service down or SLO fast burn (page) | IC within 5 min, status every 30 min, postmortem required |
| SEV2 | Degraded: slow burn, fallback model serving, a tool down | IC within 30 min, postmortem if budget impact > 10% |
| SEV3 | Ticket-level: drift, cost anomaly, budget stops rising | Next business day |

## Roles (incident command)
- **Incident commander**: owns decisions and coordination, not the keyboard.
- **Ops lead**: hands on the system, proposes and executes mitigations.
- **Comms lead**: stakeholder updates on a fixed cadence; shields the responders.
- **Scribe**: timeline in the incident channel, which becomes the postmortem timeline.

## First moves for AI workloads
1. **Mitigate before diagnosing.** Roll back the last deploy, or the last *model/prompt* change: it is a deploy too.
2. Check the gateway: is a provider failing and fallbacks are serving (quality degraded)?
3. Cut load per request: lower `AGENT_MAX_STEPS` to cut model calls during provider trouble.
4. Runaway cost: lower the team's gateway budget or rpm; that's instant and reversible.

## After
Blameless postmortem within 5 business days ([template](postmortems/TEMPLATE.md)).
Action items land in the backlog with owners; with the budget exhausted they
outrank feature work, per the [error budget policy](error-budget-policy.md).
