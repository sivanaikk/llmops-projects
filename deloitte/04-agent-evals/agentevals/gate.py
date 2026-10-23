"""Promotion gate: may this candidate agent config replace the baseline?

Reliability (pass^k) is gated harder than average quality (pass@1): an agent
that is right 90% of the time but never the same 90% is an on-call problem.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GatePolicy:
    max_pass_at_1_drop: float = 0.05
    max_pass_hat_k_drop: float = 0.0
    max_cost_increase: float = 0.30  # +30%
    max_steps_increase: float = 1.0
    min_pass_hat_k: float = 0.7  # absolute floor regardless of baseline


def evaluate(base: dict, cand: dict, policy: GatePolicy | None = None) -> list[str]:
    p = policy or GatePolicy()
    failures = []
    if cand["pass_at_1"] < base["pass_at_1"] - p.max_pass_at_1_drop:
        failures.append(f"pass@1 {base['pass_at_1']:.2f} -> {cand['pass_at_1']:.2f} (allowed drop {p.max_pass_at_1_drop:.2f})")
    if cand["pass_hat_k"] < base["pass_hat_k"] - p.max_pass_hat_k_drop:
        failures.append(f"pass^k {base['pass_hat_k']:.2f} -> {cand['pass_hat_k']:.2f} (no drop allowed)")
    if cand["pass_hat_k"] < p.min_pass_hat_k:
        failures.append(f"pass^k {cand['pass_hat_k']:.2f} below floor {p.min_pass_hat_k:.2f}")
    if base["avg_cost_usd"] and cand["avg_cost_usd"] > base["avg_cost_usd"] * (1 + p.max_cost_increase):
        failures.append(f"avg cost/run +{cand['avg_cost_usd'] / base['avg_cost_usd'] - 1:.0%} (allowed +{p.max_cost_increase:.0%})")
    if cand["avg_steps"] > base["avg_steps"] + p.max_steps_increase:
        failures.append(f"avg steps {base['avg_steps']:.1f} -> {cand['avg_steps']:.1f}")
    return failures


def render(base: dict, cand: dict, failures: list[str]) -> str:
    rows = ["pass_at_1", "pass_hat_k", "success_outcome_rate", "avg_steps", "avg_cost_usd", "latency_p95_s"]
    lines = [f"### Agent eval: `{cand['variant']}` vs `{base['variant']}`", "",
             "| metric | baseline | candidate |", "|---|---|---|"]
    lines += [f"| {m} | {base[m]} | {cand[m]} |" for m in rows]
    tags = sorted(set(base["pass_rate_by_tag"]) | set(cand["pass_rate_by_tag"]))
    lines += ["", "| tag | baseline | candidate |", "|---|---|---|"]
    lines += [f"| {t} | {base['pass_rate_by_tag'].get(t, '-')} | {cand['pass_rate_by_tag'].get(t, '-')} |" for t in tags]
    lines += ["", f"flaky in candidate: {', '.join(cand['flaky_tasks']) or 'none'}",
              f"most failed checks in candidate: {cand['failing_checks'] or 'none'}", ""]
    lines.append("**Gate: FAIL**\n" + "\n".join(f"- {f}" for f in failures) if failures else "**Gate: PASS**")
    return "\n".join(lines)
