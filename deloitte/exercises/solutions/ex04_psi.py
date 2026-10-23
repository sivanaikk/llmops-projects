import math


def psi(baseline, current, bins=10):
    s = sorted(baseline)
    edges = sorted({s[min(len(s) - 1, int(len(s) * i / bins))] for i in range(1, bins)})

    def shares(xs):
        counts = [0] * (len(edges) + 1)
        for x in xs:
            counts[sum(1 for e in edges if x > e)] += 1
        return [max(c / len(xs), 1e-4) for c in counts]

    b, c = shares(baseline), shares(current)
    return sum((ci - bi) * math.log(ci / bi) for bi, ci in zip(b, c))


def severity(value):
    return "critical" if value > 0.25 else "warning" if value >= 0.1 else "ok"
