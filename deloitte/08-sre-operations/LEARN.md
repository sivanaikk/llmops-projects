# Learn: SLOs, error budgets and running AI services

**You'll be able to:** define an SLI for a service whose requests have more than
two outcomes; turn an SLO into an error budget; write an error-budget policy
people will actually follow; run an incident with clear roles; separate toil
from engineering.
**Time:** ~60 min · **Needs:** nothing (reading + self-check)

---

## 1. The problem

"Is the service up?" is the wrong question for an AI agent. A run can succeed,
fail on the platform's side (model down, timeout), fail on the model's side
(garbled output), or be *stopped on purpose* by a guardrail (step or cost budget).
Before you can promise anything, you have to decide which of those count as failures.

## 2. Concepts

**SLI → SLO → error budget**

```
SLI     = good events / all events            e.g. runs not ending in a platform failure
SLO     = target for the SLI over a window    e.g. 99% over 28 days
budget  = 1 - SLO                             1% of runs may fail  (~ 7h of full outage in 28d)
```

**Classify every outcome before writing the SLO.** From [slo-catalogue.md](slo-catalogue.md):

| Outcome | Counts against SLO? | Why |
|---|---|---|
| `success` | no | |
| `llm_unavailable`, `deadline`, `invalid_output` | **yes** | the platform failed the user |
| `budget_*`, `loop_detected` | no, but alerted separately | the guardrail worked; the fix is a prompt or model, not paging SRE |

**The error budget is a decision tool, not a score.** It answers "can we take
risk right now?" ([error-budget-policy.md](error-budget-policy.md)):

| Budget left | What happens |
|---|---|
| > 10%, burn rates normal | ship freely |
| < 10% or burning fast | only reliability fixes, with a ticket approved by someone else |
| exhausted | feature freeze; postmortem actions first |

The policy is enforced by a machine ([02-error-budget-gate](../02-error-budget-gate/LEARN.md)),
so nobody has to win an argument at 6pm on a Friday.

**Toil** is work that is manual, repetitive, automatable and grows with the
service. [toil.md](toil.md) lists what each module in this lab automated away.

**Incident command** ([incident-response.md](incident-response.md)): an incident
commander who decides, an ops lead who acts, a comms lead who updates, a scribe
who writes the timeline. For AI incidents the first move is often "roll back the
last *model or prompt* change": those are deploys too.

## 3. Walkthrough

1. Read [slo-catalogue.md](slo-catalogue.md), then open
   [`../02-error-budget-gate/slos/agent-runtime.yaml`](../02-error-budget-gate/slos/agent-runtime.yaml).
   Find the line that encodes the outcome table above.
2. Read [production-readiness.md](production-readiness.md) and tick what *this lab*
   already satisfies. (Most of it: that's the point of the other modules.)
3. Open any alert in [`../observability/prometheus/rules/agent-alerts.yml`](../observability/prometheus/rules/agent-alerts.yml)
   and follow its `runbook_url`. Every alert links to a runbook, and a test enforces it:
   [`../tests/test_repo_consistency.py`](../tests/test_repo_consistency.py).

## 4. Exercises (open-ended)

1. **Write an SLO** for the semantic cache in Track A ([`demandbase/03-semantic-cache`](../../demandbase/03-semantic-cache/LEARN.md)).
   What is a "bad event" for a cache: a miss? a false hit? a slow lookup? Write the spec in the same YAML format.
2. **Classify a new outcome.** Suppose the agent gets an outcome `tool_permission_denied`. SLO error or not? Argue both sides, then decide.
3. **Postmortem drill.** Use [postmortems/TEMPLATE.md](postmortems/TEMPLATE.md) to write up eval run 2 from
   [04-agent-evals](../04-agent-evals/README.md#eval-history-real-runs-in-ci-qwen25-on-a-2-vcpu-github-runner-12-tasks--2-trials)
   (prompt rules made the model claim it deleted a deployment). Blameless: what allowed it?

## 5. Break it

```bash
make break-it ID=slo-counts-guardrail-stops   # predict first: what catches it?
```

## 6. Check yourself

<details><summary>1. 99.5% over 28 days: how many minutes of total outage is that?</summary>

0.005 × 28 × 24 × 60 = **201.6 minutes** (about 3.4 hours). This is also an eval task the real agent gets wrong
in CI. It keeps forgetting the ×24.
</details>

<details><summary>2. Why not count budget stops as SLO errors? They're bad user experiences.</summary>

They are, but the SLO is what SRE gets paged for and what blocks releases. Budget stops are
almost always caused by a prompt or model change, and the fix belongs to the product team.
Counting them would page the wrong people and push them to raise the limits (more cost,
more risk) instead of fixing the cause. They still get an alert: `AgentBudgetStopsHigh`.
</details>

<details><summary>3. The budget is exhausted and a security patch needs to ship. What does the policy say?</summary>

Reliability and security fixes may ship with an approved ticket (`--change-type fix --override-ticket CHG-1234`);
features may not. Rollbacks always ship. The ticket is approved by someone other than the author (segregation of duties).
</details>

<details><summary>4. Your SLO has been at 100% for six months. Good news?</summary>

Probably not. Either the SLI doesn't measure what users feel, or the SLO is so loose that
you're over-investing in reliability and could ship faster. Review the SLI and the objective with the product owner.
</details>

## 7. In the interview

* "Tell me about an SLO you defined." Use the agent outcome table: you classified outcomes
  *before* choosing a number, and you can explain why budget stops are excluded.
* "How do you stop people overriding the error budget?" Make it a machine decision (the gate),
  with a narrow, audited override for fixes only.
* "What's toil on your team?" Walk through [toil.md](toil.md) and say what you automated.

## Go further
* Google SRE Workbook, ch. 2 ("Implementing SLOs") and ch. 5 ("Alerting on SLOs")
* Google SRE Book, ch. 14 ("Managing Incidents")
