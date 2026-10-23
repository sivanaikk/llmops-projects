from math import comb


def pass_at_1(trials):
    flat = [x for ts in trials.values() for x in ts]
    return sum(flat) / len(flat)


def pass_hat_k(trials):
    return sum(all(ts) for ts in trials.values()) / len(trials)


def flaky(trials):
    return sorted(t for t, ts in trials.items() if any(ts) and not all(ts))


def pass_at_k_estimate(n, c, k):
    if n - c < k:
        return 1.0
    return 1 - comb(n - c, k) / comb(n, k)
