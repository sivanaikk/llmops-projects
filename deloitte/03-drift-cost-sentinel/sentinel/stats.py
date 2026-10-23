"""Small, dependency-free statistics for drift and anomaly detection."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


def quantiles(values: Sequence[float], n: int) -> list[float]:
    s = sorted(values)
    return [s[min(len(s) - 1, int(len(s) * i / n))] for i in range(1, n)]


def psi(baseline: Sequence[float], current: Sequence[float], bins: int = 10) -> float:
    """Population Stability Index with bins from baseline quantiles.

    Rule of thumb: < 0.1 stable, 0.1-0.25 moderate shift, > 0.25 significant.
    """
    if not baseline or not current:
        return 0.0
    edges = sorted(set(quantiles(baseline, bins)))

    def dist(xs):
        counts = [0] * (len(edges) + 1)
        for x in xs:
            i = sum(1 for e in edges if x > e)
            counts[i] += 1
        return [max(c / len(xs), 1e-4) for c in counts]  # floor avoids log(0)

    b, c = dist(baseline), dist(current)
    return sum((ci - bi) * math.log(ci / bi) for bi, ci in zip(b, c))


def distribution(items: Sequence[str]) -> dict[str, float]:
    total = len(items) or 1
    return {k: v / total for k, v in Counter(items).items()}


def js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Jensen-Shannon divergence (base 2, in [0, 1]) between categorical distributions."""
    keys = set(p) | set(q)
    m = {k: (p.get(k, 0) + q.get(k, 0)) / 2 for k in keys}

    def kl(a):
        return sum(a[k] * math.log2(a[k] / m[k]) for k in keys if a.get(k, 0) > 0)

    return (kl(p) + kl(q)) / 2


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return 0.0 if n == 0 else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def robust_z(x: float, baseline: Sequence[float]) -> float:
    """z-score using median/MAD, so a few past spikes don't hide the next one."""
    med = median(baseline)
    mad = median([abs(v - med) for v in baseline]) * 1.4826
    if mad == 0:
        return 0.0 if x == med else math.copysign(float("inf"), x - med)
    return (x - med) / mad


def two_proportion_z(k1: int, n1: int, k2: int, n2: int) -> float:
    """z statistic for 'is the rate in sample 2 different from sample 1'."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (p2 - p1) / se
