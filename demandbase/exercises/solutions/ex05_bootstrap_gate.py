import random
import statistics


def bootstrap_ci(diffs, iters=2000, alpha=0.10, seed=0):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(iters))
    return means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]


def is_regression(diffs, tolerance):
    return bootstrap_ci(diffs)[1] < -tolerance
