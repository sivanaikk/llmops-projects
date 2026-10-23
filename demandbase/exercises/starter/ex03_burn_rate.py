"""Exercise 03: SLO and burn-rate arithmetic.   (concept: 05-llm-observability/LEARN.md, 09-sre/LEARN.md)

With a 99.5% SLO over 28 days, the error budget is 0.5% of requests. Burn rate is
how fast you're spending it: error_ratio / error_budget. A burn rate of 1 uses the
budget up exactly at the end of the window; 14.4 uses 2% of the budget per hour.

Implement:
* error_budget(slo)                             -> 1 - slo
* burn_rate(error_ratio, slo)                   -> error_ratio / error_budget
* budget_spent(burn, hours, window_days=28)     -> fraction of the whole budget spent
                                                   by burning at `burn` for `hours`
* should_page(ratio_1h, ratio_5m, slo, factor=14.4)
      -> True only if BOTH windows burn faster than `factor`
         (the 1h window proves it's significant, the 5m window proves it's still happening)
* hours_to_exhaustion(remaining, burn, window_days=28)
      -> hours until `remaining` (fraction of budget) is gone at this burn rate (inf if burn <= 0)

Run:  make check EX=03
"""


def error_budget(slo: float) -> float:
    raise NotImplementedError


def burn_rate(error_ratio: float, slo: float) -> float:
    raise NotImplementedError


def budget_spent(burn: float, hours: float, window_days: int = 28) -> float:
    raise NotImplementedError


def should_page(ratio_1h: float, ratio_5m: float, slo: float, factor: float = 14.4) -> bool:
    raise NotImplementedError


def hours_to_exhaustion(remaining: float, burn: float, window_days: int = 28) -> float:
    raise NotImplementedError
