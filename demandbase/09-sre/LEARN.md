# Learn: SRE for the gateway: runbooks, game days, postmortems

**You'll be able to:** write a runbook that someone half-awake can follow; plan
and run a game day with a hypothesis; write a blameless postmortem; turn findings
into prevent/detect/mitigate actions.
**Time:** ~1.5 h (plus ~1 h for a live game day with Docker)

---

## 1. The problem

Alerts are only useful if the person paged knows what to do, and the failure
modes you've never rehearsed are the ones that hurt. SRE work is making
incidents boring: predictable, practised, and followed by real fixes.

## 2. Concepts

**A runbook** ([runbooks/](runbooks/)) answers, in order: what's the impact, how do I confirm it, what do I
do first (mitigate before diagnosing), and how do I know it's fixed. Every alert links to one.

**A game day** is a planned experiment:

```
hypothesis  "primary provider down → chat users see no errors; traffic shifts to the
             secondary within one cooldown; LLMPrimaryProviderDegraded fires; nobody is paged"
inject      tools/game_day.py --scenario primary-outage
observe     error rate, served_by, which alerts fired
write up    what matched, what didn't, and actions
```

The plan in [postmortems/2026-10-gameday-primary-provider-outage.md](postmortems/2026-10-gameday-primary-provider-outage.md)
already found two gaps by walking the scenario through the config, before running anything:
`embed-small` has a single deployment (RAG goes down with the primary), and availability
alerts only look at the *global* error ratio.

**Blameless postmortems** ([TEMPLATE.md](postmortems/TEMPLATE.md)) ask what the system *allowed*,
not who slipped, and end with actions typed as prevent / detect / mitigate.

## 3. Walkthrough

1. Pick an alert in [`../05-llm-observability/prometheus/rules/slo-alerts.yml`](../05-llm-observability/prometheus/rules/slo-alerts.yml)
   and follow its runbook. Could you act on it at 3am?
2. Run the no-Docker failover drill: `python 01-llm-gateway/e2e/run_e2e.py`, which injects a primary
   outage into mock providers and checks the hypothesis automatically.
3. With Docker: `make up`, open Grafana, then `make gameday SCENARIO=primary-outage` and fill in the "Observed" column of the game-day plan.

## 4. Exercises (open-ended)

1. **Fix the gaps the game day found:** add a second `embed-small` deployment, and write a per-model-group
   burn-rate alert with a promtool test.
2. **Write a runbook** for a failure that has none yet: "Redis down" (rate limits become per-pod, the cache misses, cooldowns aren't shared).
3. **Postmortem drill:** pretend the Aadhaar false positive (Track A module 02) reached production and
   redacted order numbers for a day. Write the postmortem. What *detected* it, and what should have?

## 5. Check yourself

<details><summary>1. Why "mitigate before diagnosing"?</summary>

Users are hurting now; root cause can wait. Rolling back the last change or failing over usually ends the
impact in minutes. Diagnosis happens afterwards, with the timeline intact.
</details>

<details><summary>2. A game day found nothing wrong. Wasted?</summary>

No: it raised confidence in a specific failure path, rehearsed the team, and checked that the alerts and
runbooks match reality. But if game days never find anything, make the scenarios harder.
</details>

## 6. In the interview

* "Tell me about an incident you ran." Use the structure: detection, impact, mitigation, root cause, what you changed.
* "How do you prepare for incidents?" Runbooks linked from alerts, game days with hypotheses, and action items that actually get done.

## Go further
* Google SRE Book ch. 15 ("Postmortem Culture"); PagerDuty incident response docs
