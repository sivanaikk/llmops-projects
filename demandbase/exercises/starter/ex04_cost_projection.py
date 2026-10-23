"""Exercise 04: FinOps early warning.   (concept: 04-cost-control/LEARN.md)

Hard budgets at the gateway reject requests once money is gone: correct, but
by then the feature is down. Early warning projects spend forward.

* shadow_price(model, prompt_tokens, completion_tokens, table) -> USD
      table: {model: (usd_per_1M_input, usd_per_1M_output)}; unknown model -> 0.0
* project_month_end(spend_so_far, day_of_month, hour, days_in_month) -> USD
      elapsed_days = (day_of_month - 1) + hour/24, at least 1/24 (avoid absurd
      projections in the first hour); linear run-rate projection to the month end.
* alert(spend, projected, budget) -> list of (severity, message):
      ("critical", ...) if spend >= budget
      else ("warning", ...) if spend >= 0.8*budget
      else ("info", ...) if spend >= 0.5*budget  (only the highest threshold reached)
      plus ("warning", "on pace ...") if projected > budget and spend < budget

Run:  make check EX=04
"""


def shadow_price(model: str, prompt_tokens: int, completion_tokens: int, table: dict) -> float:
    raise NotImplementedError


def project_month_end(spend_so_far: float, day_of_month: int, hour: int, days_in_month: int) -> float:
    raise NotImplementedError


def alert(spend: float, projected: float, budget: float) -> list[tuple[str, str]]:
    raise NotImplementedError
