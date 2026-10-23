# Learn: catching quiet AI failures (drift and cost anomalies)

**You'll be able to:** explain why AI systems fail without errors; measure drift
with PSI and Jensen-Shannon divergence; detect anomalies robustly (median/MAD);
pair statistical significance with effect size so alerts mean something.
**Time:** ~1.5 h · **Needs:** Python only

---

## 1. The problem

Most AI incidents don't throw a 500. Users start pasting logs into questions; a
retrieval change triples prompt size; a model swap breaks the output format 30%
of the time. Availability stays green. The only signal is a **distribution shifting**.

## 2. Concepts

| Detector | Statistic | Rule of thumb |
|---|---|---|
| numeric drift (question size, tokens, steps) | **PSI** = Σ (cᵢ − bᵢ) · ln(cᵢ / bᵢ) over baseline-decile bins | < 0.1 stable · 0.1–0.25 moderate · > 0.25 significant |
| categorical drift (outcomes, tools, model) | **Jensen-Shannon divergence** (0 = identical, 1 = disjoint) | per signal |
| rate shift (invalid output, budget stops, tool errors) | two-proportion **z-test** + a minimum increase | z > 5 and at least +2 points |
| cost per run | median ratio vs baseline | > 1.3× warn, > 2× critical |
| hourly spend | **robust z** (median, MAD) **and** ≥ 1.5× the median hour | both must hold |

**Why both significance and effect size?** This lab shipped with z-score-only
spend detection, and it flagged ordinary 20% traffic growth as critical. A quiet
baseline has a tiny MAD, so any change looks huge in z terms. The fix (and a
regression test) requires the hour to also be materially bigger. A significant
change and a change that matters are different things.

**Which signals move tells you who changed:**

| Scenario | Question size | Prompt tokens | Cost/run | Read it as |
|---|---|---|---|---|
| prompt drift | **up** | up | slightly up | users changed |
| cost spike | flat | **up** | **up** | *we* changed (retrieval, prompt) |

## 3. Walkthrough

```bash
cd ..   # deloitte/
make sentinel-demo
```

Real output, `cost_spike` scenario (exit code 1 because something is critical):

```
| CRIT | numeric_drift | prompt_tokens | prompt_tokens: PSI 8.294 (median 1369.0 -> 5696.0) |
| CRIT | cost_anomaly | cost_per_run | median cost per run $0.000424 -> $0.001306 (3.08x) |
| CRIT | cost_anomaly | hourly_spend | worst hour 2026-10-23T07: robust z 43.2 vs 72 baseline hours |
| ok   | numeric_drift | question_chars | question_chars: PSI 0.040 (median 66.0 -> 66.5) |
```

Question size is flat and prompt tokens 4x'd: the system changed, not the users.

Read: [`sentinel/stats.py`](sentinel/stats.py) (≈ 60 lines of statistics) →
[`sentinel/detectors.py`](sentinel/detectors.py) `run_all` → [`sentinel/synth.py`](sentinel/synth.py)
(how each failure scenario is simulated). On real data: `python -m sentinel.monitor --runs runs.jsonl`
using the agent's run log (`AGENT_RUN_LOG`).

## 4. Exercises

```bash
make check EX=04     # implement PSI and its severity cut-offs
```

Challenges:
1. Add a scenario `language_shift` (questions suddenly in Hindi) to `synth.py`. Which existing
   signal catches it, if any? What new feature would you log to catch it reliably?
2. The detectors compare two windows. Add **seasonality**: compare 10:00 today with 10:00 on the same
   weekday last week. When does this matter for an internal tool vs a customer-facing feature?
3. `--prom-textfile` writes gauges; wire them into the `AIDriftOrCostAnomaly` alert and add a promtool test.

## 5. Break it

```bash
make break-it ID=sentinel-zscore-only        # the real false-positive bug
make break-it ID=sentinel-psi-log-zero
```

## 6. Check yourself

<details><summary>1. Why median/MAD instead of mean/stdev for spend anomalies?</summary>

Past spikes inflate the mean and the stdev, which hides the next spike. Median and MAD barely move with a
few outliers, so a new spike still stands out.
</details>

<details><summary>2. PSI is 0.4 on question length. Incident?</summary>

Not by itself: it means users ask differently. Check whether quality signals moved (invalid output, budget
stops) and whether the evals still represent real inputs. Drift is a ticket ("update evals and budgets"),
not a page.
</details>

<details><summary>3. Why refuse to judge fewer than 50 baseline runs?</summary>

With small samples, every statistic is noisy and the detector would flap. Under-sampled windows return
"not enough data" instead of a confident wrong answer.
</details>

## 7. In the interview

* "How do you monitor AI quality in production?" Distribution signals, not just errors: input drift,
  behaviour drift, quality-rate shifts, cost. Then the "who changed?" table.
* "Tell me about a noisy alert you fixed." The z-score-only false positive and the effect-size fix.

## Go further
* Evidently AI / NannyML docs on PSI, JS divergence and drift in production ML
* "Robust statistics": MAD-based outlier detection
