"""Detectors for the ways AI workloads fail quietly.

Nothing here throws a 500. Each failure mode shows up only as a shift in a
distribution, which is why plain availability SLOs miss it:

* input drift       - users ask different things (longer, new topics) than the system was evaluated on
* behaviour drift   - the agent uses tools differently, takes more steps, ends with other outcomes
* quality signals   - more protocol violations / budget stops / tool errors (often a model or prompt change)
* cost anomalies    - spend per run or per hour jumps (prompt bloat, loops, model swap)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import stats

SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "critical": 3}


@dataclass
class Finding:
    detector: str
    signal: str
    severity: str
    value: float
    threshold: str
    message: str
    details: dict = field(default_factory=dict)


def _sev(value: float, warn: float, crit: float) -> str:
    return "critical" if value >= crit else "warning" if value >= warn else "ok"


def numeric_drift(base: list[dict], cur: list[dict], feature: str, warn=0.1, crit=0.25) -> Finding:
    b = [float(r[feature]) for r in base if r.get(feature) is not None]
    c = [float(r[feature]) for r in cur if r.get(feature) is not None]
    v = stats.psi(b, c)
    return Finding("numeric_drift", feature, _sev(v, warn, crit), round(v, 4), f"PSI warn {warn} / crit {crit}",
                   f"{feature}: PSI {v:.3f} (median {stats.median(b):.1f} -> {stats.median(c):.1f})",
                   {"baseline_median": stats.median(b), "current_median": stats.median(c)})


def categorical_drift(base: list[dict], cur: list[dict], feature: str, warn=0.05, crit=0.15, explode=False) -> Finding:
    def items(rows):
        out = []
        for r in rows:
            v = r.get(feature)
            out.extend(v if explode and isinstance(v, list) else [v])
        return [str(x) for x in out]

    p, q = stats.distribution(items(base)), stats.distribution(items(cur))
    v = stats.js_divergence(p, q)
    moved = sorted(set(p) | set(q), key=lambda k: abs(q.get(k, 0) - p.get(k, 0)), reverse=True)[:3]
    desc = ", ".join(f"{k} {p.get(k, 0):.0%}->{q.get(k, 0):.0%}" for k in moved)
    return Finding("categorical_drift", feature, _sev(v, warn, crit), round(v, 4), f"JS warn {warn} / crit {crit}",
                   f"{feature}: JS divergence {v:.3f} ({desc})", {"baseline": p, "current": q})


def rate_shift(base: list[dict], cur: list[dict], name: str, predicate, warn_z=3.0, crit_z=5.0, min_delta=0.02) -> Finding:
    k1, n1 = sum(1 for r in base if predicate(r)), len(base)
    k2, n2 = sum(1 for r in cur if predicate(r)), len(cur)
    z = stats.two_proportion_z(k1, n1, k2, n2)
    r1, r2 = (k1 / n1 if n1 else 0), (k2 / n2 if n2 else 0)
    # Only increases matter, and only if big enough to care about.
    sev = _sev(z, warn_z, crit_z) if (r2 - r1) >= min_delta else "ok"
    return Finding("rate_shift", name, sev, round(z, 2), f"z warn {warn_z} / crit {crit_z}, min +{min_delta:.0%}",
                   f"{name}: {r1:.1%} -> {r2:.1%} (z={z:.1f})", {"baseline_rate": r1, "current_rate": r2})


def cost_per_run(base: list[dict], cur: list[dict], warn_ratio=1.3, crit_ratio=2.0) -> Finding:
    b = stats.median([r["cost_usd"] for r in base])
    c = stats.median([r["cost_usd"] for r in cur])
    ratio = c / b if b else (1.0 if c == 0 else float("inf"))
    return Finding("cost_anomaly", "cost_per_run", _sev(ratio, warn_ratio, crit_ratio), round(ratio, 3),
                   f"median ratio warn {warn_ratio}x / crit {crit_ratio}x",
                   f"median cost per run ${b:.6f} -> ${c:.6f} ({ratio:.2f}x)", {"baseline": b, "current": c})


def hourly_spend(base: list[dict], cur: list[dict], warn_z=4.0, crit_z=8.0, min_ratio=1.5) -> Finding:
    """An hour is anomalous only if it is both statistically unusual (robust z)
    and materially bigger (min_ratio x the median hour). z alone flags ordinary
    traffic growth whenever baseline variance is low."""
    def by_hour(rows):
        out: dict[str, float] = {}
        for r in rows:
            out[r["ts"][:13]] = out.get(r["ts"][:13], 0.0) + r["cost_usd"]
        return out

    b = list(by_hour(base).values())
    c = by_hour(cur)
    worst_hour, worst_z = None, 0.0
    med = stats.median(b)
    for hour, spend in c.items():
        z = stats.robust_z(spend, b) if len(b) >= 6 else 0.0
        if med and spend < min_ratio * med:
            continue
        if z > worst_z:
            worst_hour, worst_z = hour, z
    shown = min(worst_z, 999.0)
    return Finding("cost_anomaly", "hourly_spend", _sev(worst_z, warn_z, crit_z), round(shown, 2),
                   f"robust z warn {warn_z} / crit {crit_z}, and >= {min_ratio}x median hour",
                   f"worst hour {worst_hour or '-'}: robust z {shown:.1f} vs {len(b)} baseline hours",
                   {"worst_hour": worst_hour})


def run_all(base: list[dict], cur: list[dict]) -> list[Finding]:
    return [
        numeric_drift(base, cur, "question_chars"),
        numeric_drift(base, cur, "prompt_tokens"),
        numeric_drift(base, cur, "steps"),
        categorical_drift(base, cur, "outcome"),
        categorical_drift(base, cur, "tools", explode=True),
        categorical_drift(base, cur, "model", warn=0.01, crit=0.5),
        rate_shift(base, cur, "invalid_output_rate", lambda r: r.get("invalid_outputs", 0) > 0),
        rate_shift(base, cur, "budget_stop_rate", lambda r: str(r.get("outcome", "")).startswith("budget_")
                   or r.get("outcome") == "loop_detected"),
        rate_shift(base, cur, "tool_error_rate", lambda r: r.get("tool_errors", 0) > 0),
        cost_per_run(base, cur),
        hourly_spend(base, cur),
    ]
