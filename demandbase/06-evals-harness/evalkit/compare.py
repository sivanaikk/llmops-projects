"""Compare a candidate against the baseline and decide whether it may ship.

With ~16-200 examples, a 3-point difference in a mean score is often noise.
We compute a paired bootstrap confidence interval on the per-example
difference and only call it a regression if the *upper* bound is below the
allowed tolerance, i.e. we are confident it got worse.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from .runner import RunResult


@dataclass
class MetricDelta:
    metric: str
    baseline: float
    candidate: float
    delta: float
    ci_low: float
    ci_high: float
    regression: bool


@dataclass
class Gate:
    """Per-metric tolerance: how much worse the candidate may be (absolute)."""

    tolerances: dict[str, float]
    max_error_rate: float = 0.05
    max_p95_latency_increase: float = 0.5  # +50%


DEFAULT_GATE = Gate({"fact_recall": 0.05, "abstention_correct": 0.10, "retrieval_hit": 0.0, "judge_faithfulness": 0.10})


def paired_bootstrap(diffs: list[float], iters: int = 2000, alpha: float = 0.10, seed: int = 0) -> tuple[float, float]:
    if not diffs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(statistics.fmean(rng.choices(diffs, k=n)) for _ in range(iters))
    return means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]


def compare(base: RunResult, cand: RunResult, gate: Gate = DEFAULT_GATE) -> tuple[list[MetricDelta], list[str]]:
    b_rows = {r.id: r for r in base.rows}
    pairs = [(b_rows[r.id], r) for r in cand.rows if r.id in b_rows]
    metrics = sorted({k for _, r in pairs for k in r.scores} & {k for b, _ in pairs for k in b.scores})

    deltas, failures = [], []
    for m in metrics:
        diffs = [c.scores[m] - b.scores[m] for b, c in pairs]
        lo, hi = paired_bootstrap(diffs)
        bm = statistics.fmean(b.scores[m] for b, _ in pairs)
        cm = statistics.fmean(c.scores[m] for _, c in pairs)
        tol = gate.tolerances.get(m)
        regression = tol is not None and hi < -tol
        deltas.append(MetricDelta(m, round(bm, 4), round(cm, 4), round(cm - bm, 4), round(lo, 4), round(hi, 4), regression))
        if regression:
            failures.append(f"{m} regressed: {bm:.3f} -> {cm:.3f} (90% CI of delta [{lo:+.3f}, {hi:+.3f}], tolerance {tol})")

    err_rate = cand.summary.get("errors", 0) / max(cand.summary.get("n", 1), 1)
    if err_rate > gate.max_error_rate:
        failures.append(f"error rate {err_rate:.1%} > {gate.max_error_rate:.0%}")
    b95, c95 = base.summary.get("latency_p95_s", 0), cand.summary.get("latency_p95_s", 0)
    if b95 and c95 > b95 * (1 + gate.max_p95_latency_increase):
        failures.append(f"p95 latency {b95:.2f}s -> {c95:.2f}s (> +{gate.max_p95_latency_increase:.0%})")
    return deltas, failures


def render_markdown(base: RunResult, cand: RunResult, deltas: list[MetricDelta], failures: list[str]) -> str:
    lines = [
        f"### Eval: `{cand.variant}` vs `{base.variant}`",
        "",
        "| metric | baseline | candidate | delta | 90% CI | |",
        "|---|---|---|---|---|---|",
    ]
    for d in deltas:
        flag = "REGRESSION" if d.regression else ("better" if d.ci_low > 0 else "~")
        lines.append(f"| {d.metric} | {d.baseline:.3f} | {d.candidate:.3f} | {d.delta:+.3f} | [{d.ci_low:+.3f}, {d.ci_high:+.3f}] | {flag} |")
    bs, cs = base.summary, cand.summary
    lines += [
        "",
        f"latency p95: {bs.get('latency_p95_s')}s -> {cs.get('latency_p95_s')}s | "
        f"avg prompt tokens: {bs.get('avg_prompt_tokens')} -> {cs.get('avg_prompt_tokens')} | "
        f"errors: {bs.get('errors')} -> {cs.get('errors')}",
        "",
        "**Gate: FAIL**\n" + "\n".join(f"- {f}" for f in failures) if failures else "**Gate: PASS**",
    ]
    return "\n".join(lines)
