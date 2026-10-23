"""Exercise 05: is the candidate really worse, or is it noise?   (concept: 06-evals-harness/LEARN.md)

Two prompt versions scored on the same N examples. diffs[i] = candidate_i - baseline_i.

* bootstrap_ci(diffs, iters=2000, alpha=0.10, seed=0) -> (low, high)
      resample `diffs` with replacement (same size) `iters` times using
      random.Random(seed).choices, take the mean of each resample, sort the means,
      return the alpha/2 and 1 - alpha/2 percentiles:
      means[int(alpha/2*iters)], means[int((1-alpha/2)*iters) - 1]
* is_regression(diffs, tolerance) -> True only if the WHOLE interval is below -tolerance
      (i.e. high < -tolerance: we're confident it got worse by more than we accept)

Run:  make check EX=05
"""


def bootstrap_ci(diffs: list[float], iters: int = 2000, alpha: float = 0.10, seed: int = 0) -> tuple[float, float]:
    raise NotImplementedError


def is_regression(diffs: list[float], tolerance: float) -> bool:
    raise NotImplementedError
