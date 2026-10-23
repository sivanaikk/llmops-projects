"""Exercise 04: Population Stability Index (PSI) for drift detection.

PSI compares the distribution of a feature (e.g. question length) in a current
window against a baseline window:

    1. bin edges = the baseline's deciles (quantiles at 10%, 20%, ... 90%)
    2. b_i, c_i  = share of baseline / current values in each bin
                   (value goes in the first bin whose upper edge it doesn't exceed;
                    floor each share at 1e-4 so log(0) can't happen)
    3. PSI = sum_i (c_i - b_i) * ln(c_i / b_i)

Rule of thumb: < 0.1 stable, 0.1-0.25 moderate drift, > 0.25 significant.

Also implement `severity(psi)` -> "ok" | "warning" | "critical" with those cut-offs.

Run:  make check EX=04
"""


def psi(baseline: list[float], current: list[float], bins: int = 10) -> float:
    raise NotImplementedError


def severity(value: float) -> str:
    raise NotImplementedError
