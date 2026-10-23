"""Budgets, burn-rate forecasting and alerting.

LiteLLM enforces *hard* budgets on virtual keys/teams (requests get 429'd once
`max_budget` is hit). That's the backstop. This module is the early warning:
it projects month-end spend from the current run-rate so a team hears about an
overrun on day 9, not when their feature starts failing on day 23.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class Budget:
    team: str
    monthly_usd: float
    alert_thresholds: list[float] = field(default_factory=lambda: [0.5, 0.8, 1.0])
    owner: str = ""


@dataclass
class BudgetAlert:
    team: str
    severity: str  # "info" | "warning" | "critical"
    message: str
    spend_usd: float
    projected_usd: float
    budget_usd: float


def load_budgets(path: str | Path) -> dict[str, Budget]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return {
        team: Budget(team, float(b["monthly_usd"]), b.get("alert_thresholds", [0.5, 0.8, 1.0]), b.get("owner", ""))
        for team, b in raw.get("budgets", {}).items()
    }


def project_month_end(spend_to_date: float, now: datetime) -> float:
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    elapsed = (now.day - 1) + (now.hour * 3600 + now.minute * 60 + now.second) / 86400
    elapsed = max(elapsed, 1 / 24)  # avoid wild projections in the first hour
    return spend_to_date / elapsed * days_in_month


def evaluate(budget: Budget, spend_to_date: float, now: datetime) -> list[BudgetAlert]:
    projected = project_month_end(spend_to_date, now)
    used = spend_to_date / budget.monthly_usd if budget.monthly_usd else 0.0
    alerts: list[BudgetAlert] = []

    crossed = [t for t in sorted(budget.alert_thresholds) if used >= t]
    if crossed:
        t = crossed[-1]
        sev = "critical" if t >= 1.0 else "warning" if t >= 0.8 else "info"
        alerts.append(
            BudgetAlert(budget.team, sev, f"{budget.team} has used {used:.0%} of its ${budget.monthly_usd:,.2f} monthly LLM budget",
                        spend_to_date, projected, budget.monthly_usd)
        )
    if projected > budget.monthly_usd and used < 1.0:
        alerts.append(
            BudgetAlert(budget.team, "warning",
                        f"{budget.team} is on pace to spend ${projected:,.2f} vs ${budget.monthly_usd:,.2f} budget "
                        f"({projected / budget.monthly_usd:.0%})", spend_to_date, projected, budget.monthly_usd)
        )
    return alerts
