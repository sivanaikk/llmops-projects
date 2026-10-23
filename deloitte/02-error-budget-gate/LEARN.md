# Learn: burn rates, SLOs as code, and release gates (Go)

**You'll be able to:** compute burn rates and budget consumption; explain why
alerts use two windows; generate Prometheus rules from an SLO spec; implement a
release gate that blocks risky deploys but never blocks a rollback.
**Time:** ~2 h · **Needs:** Go 1.22+ (promtool optional)

---

## 1. The problem

You have an SLO. Now you need two automatic behaviours:
1. **Page** someone when the budget is burning fast enough to matter, and *only* then.
2. **Stop releases** when there's no budget left to spend on risk.

Doing either by hand fails: thresholds drift, and every release becomes a negotiation.

## 2. Concepts

**Burn rate** = how fast you're spending the budget, relative to plan:

```
burn = error_ratio / (1 - objective)

SLO 99% (budget 1%):  error ratio 1%  -> burn 1    (budget lasts exactly the window)
                      error ratio 14.4% -> burn 14.4 (2% of a 30-day budget gone in 1 hour)
budget spent = burn × hours / (window_days × 24)
```

**Why two windows?** One long window alone keeps firing long after you've
recovered. One short window alone fires on every blip. So page only when
**both** are high:

| Alert | Long window | Short window | Burn | Means |
|---|---|---|---|---|
| `SLOFastBurn` (page) | 1h | 5m | > 14.4 | 2% of budget per hour, and still happening |
| `SLOSlowBurn` (page) | 6h | 30m | > 6 | 5% of budget per 6h |
| `SLOBudgetLeak` (ticket) | 3d | 6h | > 1 | spending faster than it accrues |

**SLOs as code.** One YAML spec produces the alert rules *and* drives the gate,
so the alerts and the gate can't disagree:

```
slos/agent-runtime.yaml ─► budgetgate rules ─► Prometheus recording + alert rules
                        └► budgetgate check ─► exit 0 (ship) / 1 (blocked)
```

**Gate policy** ([slo/gate.go](slo/gate.go) `Evaluate`): admit unless budget <
minimum, 1h burn > 14.4, or 6h burn > 6. Exceptions: rollbacks always pass; a *fix*
with an approved ticket passes; Prometheus unreachable = deny (fail closed) for tier-1.

## 3. Walkthrough

```bash
go test ./...                                  # 10 tests, incl. a fake Prometheus server
go run ./cmd/budgetgate rules --slos slos | head -20
```

You'll see the recording rules for every window, then alerts like:

```yaml
- alert: SLOFastBurn
  expr: (slo:error_ratio:rate1h{service="agent-runtime", slo="availability"} / 0.01 > 14.4)
    and (slo:error_ratio:rate5m{service="agent-runtime", slo="availability"} / 0.01 > 14.4)
```

`/ 0.01` is the error budget (1 − 0.99), so `ratio / 0.01` is the burn rate.

Now read the decision logic in the order a request flows through it:
[`slo/spec.go`](slo/spec.go) `Load` + `Validate` → [`slo/gate.go`](slo/gate.go) `Evaluate`
→ [`cmd/budgetgate/main.go`](cmd/budgetgate/main.go) `check`. Notice that `Evaluate` queries the
*raw* SLI, not the recording rules, so the gate works before the rules are even deployed.

The alert rules themselves are unit-tested with promtool
([`../observability/prometheus/rules/alerts.test.yml`](../observability/prometheus/rules/alerts.test.yml)):
5% errors for an hour does **not** fast-burn page; 30% does.

## 4. Exercises

**B-07 (Go): build the decision function yourself.**
```bash
cd ..                          # deloitte/
make check-go                  # fails: panic "TODO: implement BurnRate"
$EDITOR exercises/go/burnrate/starter.go
make check-go                  # until ok
make check-go SOLUTION=1       # reference
```

Challenges:
1. Add an SLO for latency ("95% of runs finish under 20s") using the histogram
   `agent_run_duration_seconds_bucket`. What changes in `SLI` when the good events
   are "bucket le=20" rather than "not an error"?
2. Add `budgetgate explain --slo ... --ratio-1h 0.2`, which prints the burn maths for a
   hypothetical ratio. Useful for teaching on-call.
3. Today the gate is fail-closed for `on_error`. When would you choose fail-open?

## 5. Break it

```bash
make break-it ID=gate-blocks-rollbacks
make break-it ID=gate-fails-open
make break-it ID=gate-ticket-unlocks-features
make break-it ID=slo-edited-rules-not-regenerated
make break-it ID=alert-threshold-typo          # needs promtool
```

## 6. Check yourself

<details><summary>1. Error ratio 3% on a 99.5% SLO. Burn rate? Page?</summary>

Burn = 0.03 / 0.005 = **6**. Not a fast-burn page (needs > 14.4). If it lasts 6h and the last 30m is
also above 6, `SLOSlowBurn` pages. Over 6h it spends 6 × 6 / 672 ≈ 5.4% of the 28-day budget.
</details>

<details><summary>2. Why does the gate always admit rollbacks?</summary>

During an incident the burn rate is high, so a strict gate would block every change, including the
rollback that ends the incident. Blocking the way out makes the outage longer.
</details>

<details><summary>3. Why query the raw SLI instead of the `slo:error_ratio` recording rules?</summary>

So the gate works on day one, before the rules are deployed, and doesn't depend on the rule evaluation
pipeline being healthy. One less moving part in a safety check.
</details>

<details><summary>4. What's wrong with a single 1h window and threshold 14.4?</summary>

It keeps paging for up to an hour after recovery (the bad minutes are still in the window), and it can't
tell an ongoing outage from one that already ended. The 5m window confirms it's still happening.
</details>

## 7. In the interview

* Explain 14.4 from first principles: "2% of a 30-day budget in one hour: 0.02 × 720h = 14.4."
* "How do you gate deployments on reliability?" Spec → rules + gate; fail-closed for tier-1; rollbacks
  exempt; ticketed fixes only; same check in CI and in the Argo CD PreSync hook.
* The drift bug: editing the spec without regenerating means alerts and gate disagree. CI regenerates and diffs.

## Go further
* Google SRE Workbook ch. 5, "Alerting on SLOs" (the multiwindow, multi-burn-rate table)
* Sloth / Pyrra: open-source SLO-to-rules generators, the production versions of `budgetgate rules`
