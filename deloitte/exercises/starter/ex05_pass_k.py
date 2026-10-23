"""Exercise 05: measuring a non-deterministic agent.

`trials` maps task id -> list of booleans, one per trial (True = passed).

* pass_at_1(trials): mean pass rate over ALL trials.
* pass_hat_k(trials): share of tasks that passed in EVERY trial (reliability).
* flaky(trials): sorted task ids that passed some trials but not all.
* pass_at_k_estimate(n, c, k): the unbiased pass@k estimator (Chen et al. 2021):
      probability that at least one of k samples drawn from n trials (c correct) passes
      = 1 - C(n - c, k) / C(n, k)          (1.0 if n - c < k)

Why both? An agent that is right 90% of the time but never on the same 90% of
tasks has a high pass@1 and a low pass^k. Users and SLOs feel pass^k.

Run:  make check EX=05
"""


def pass_at_1(trials: dict[str, list[bool]]) -> float:
    raise NotImplementedError


def pass_hat_k(trials: dict[str, list[bool]]) -> float:
    raise NotImplementedError


def flaky(trials: dict[str, list[bool]]) -> list[str]:
    raise NotImplementedError


def pass_at_k_estimate(n: int, c: int, k: int) -> float:
    raise NotImplementedError
