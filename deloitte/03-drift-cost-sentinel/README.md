# 03 · Drift and cost-anomaly sentinel (`sentinel`)

> JD: *"Learn product domains quickly, including AI failure modes such as drift
> and cost anomalies"*, *"cloud/AI cost engineering"*.

AI workloads mostly fail **quietly**: no 5xx, just a shift in a distribution.
The sentinel compares a current window of agent runs (the JSONL run log from 01)
against a baseline window:

| Detector | Signals | Statistic |
|---|---|---|
| input drift | question size, prompt tokens | PSI (baseline-quantile bins) |
| behaviour drift | steps, outcome mix, tool mix, model served | PSI / Jensen-Shannon divergence |
| quality signals | invalid-output, budget/loop-stop, tool-error rates | two-proportion z-test **and** a minimum effect size |
| cost anomalies | median cost per run, hourly spend | ratio vs baseline; robust z (median/MAD) **and** ≥ 1.5x the median hour |

Each synthetic failure scenario flags exactly the signals it should (tests assert this):

| Scenario | Flags (critical) | Stays quiet |
|---|---|---|
| `normal` | nothing | everything |
| `prompt_drift` (users paste logs) | question size | cost per run (< 2x) |
| `model_regression` (0.5B swap breaks protocol) | invalid output, budget stops, outcomes, model, steps | |
| `cost_spike` (retrieval stuffs context) | prompt tokens, cost per run, hourly spend | question size: users didn't change, **we** did |
| `tool_outage` | tool-error rate, tool mix | |

An earlier version flagged ordinary 20% traffic growth as a spend anomaly:
low-variance baselines make z-scores jumpy. Hourly spend now also has to be
materially larger (≥ 1.5x the median hour), and there's a regression test for it.

```bash
python -m sentinel.monitor --demo cost_spike                     # exit 1 on critical
python -m sentinel.monitor --runs runs.jsonl --baseline-hours 72 --current-hours 6 --prom-textfile sentinel.prom
```

`--prom-textfile` (or a Pushgateway) feeds `sentinel_signal_severity`, which
`AIDriftOrCostAnomaly` alerts on.
