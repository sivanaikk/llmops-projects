"""Showback report: who spent what, on which model, and what caching saved.

    python -m costwatch.report --budgets budgets.yaml            # DuckDB file from env
    COSTWATCH_SINK=clickhouse python -m costwatch.report ...       # production
    python -m costwatch.report --demo                              # synthetic data
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import budgets as budget_mod
from .events import UsageEvent
from .pricing import price
from .sinks import DuckDBSink, Sink, from_env

MONTH_FILTER = "ts >= date_trunc('month', now())"

QUERIES = {
    "by_team": f"""
        SELECT team, count(*) AS calls, sum(total_tokens) AS tokens, round(sum(cost_usd), 4) AS cost_usd
        FROM llm_usage WHERE {MONTH_FILTER} GROUP BY team ORDER BY cost_usd DESC""",
    "by_team_model": f"""
        SELECT team, model, count(*) AS calls, round(sum(cost_usd), 4) AS cost_usd,
               round(avg(prompt_tokens), 1) AS avg_prompt_tokens
        FROM llm_usage WHERE {MONTH_FILTER} GROUP BY team, model ORDER BY cost_usd DESC""",
    "by_feature": f"""
        SELECT team, feature, count(*) AS calls, round(sum(cost_usd), 4) AS cost_usd
        FROM llm_usage WHERE {MONTH_FILTER} GROUP BY team, feature ORDER BY cost_usd DESC LIMIT 10""",
    # Cache hits are logged at the price the call *would* have cost, so the
    # savings figure is directly comparable to spend.
    "cache_savings": f"""
        SELECT team, sum(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits, count(*) AS calls,
               round(sum(CASE WHEN cache_hit THEN cost_usd ELSE 0 END), 4) AS saved_usd
        FROM llm_usage WHERE {MONTH_FILTER} GROUP BY team ORDER BY saved_usd DESC""",
}


def billable_spend(sink: Sink) -> dict[str, float]:
    rows = sink.query(
        f"SELECT team, sum(cost_usd) AS spend FROM llm_usage WHERE {MONTH_FILTER} AND NOT cache_hit GROUP BY team"
    )
    return {r["team"]: float(r["spend"]) for r in rows}


def _table(rows: list[dict]) -> str:
    if not rows:
        return "  (no data)"
    cols = list(rows[0])
    widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
    line = lambda vals: "  " + "  ".join(str(v).ljust(w) for v, w in zip(vals, widths))  # noqa: E731
    return "\n".join([line(cols), line("-" * w for w in widths), *(line(r[c] for c in cols) for r in rows)])


def seed_demo(sink: Sink, n: int = 2000, seed: int = 7) -> None:
    rng = random.Random(seed)
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    span = max((now - start).total_seconds(), 3600)
    teams = {
        "account-intel": (["account-summary", "email-draft"], ["chat-small", "embed-small"], 0.55),
        "internal-tools": (["slack-bot", "code-review"], ["chat-small", "chat-tiny"], 0.30),
        "data-science": (["eval-runs"], ["judge", "chat-small"], 0.15),
    }
    events = []
    for _ in range(n):
        team = rng.choices(list(teams), weights=[t[2] for t in teams.values()])[0]
        features, models, _ = teams[team]
        model = rng.choice(models)
        pt = int(rng.lognormvariate(6.5, 0.6))
        ct = 0 if model.startswith("embed") else int(rng.lognormvariate(5, 0.5))
        events.append(UsageEvent(
            request_id=str(uuid.uuid4()), team=team, model=model, provider_model=f"ollama/{model}",
            prompt_tokens=pt, completion_tokens=ct, cost_usd=price(model, pt, ct) * 200,  # scaled up to look like real traffic
            feature=rng.choice(features), cache_hit=rng.random() < 0.18,
            ts=start + timedelta(seconds=rng.uniform(0, span)),
        ))
    sink.write(events)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", type=Path, default=Path(__file__).resolve().parents[1] / "budgets.yaml")
    ap.add_argument("--demo", action="store_true", help="use an in-memory DB with synthetic traffic")
    args = ap.parse_args()

    sink: Sink = DuckDBSink() if args.demo else from_env()
    if args.demo:
        seed_demo(sink)

    for name, sql in QUERIES.items():
        print(f"\n== {name} ==\n{_table(sink.query(sql))}")

    budgets = budget_mod.load_budgets(args.budgets)
    now = datetime.now(UTC)
    print("\n== budget alerts ==")
    any_alert = False
    for team, spend in billable_spend(sink).items():
        if team in budgets:
            for a in budget_mod.evaluate(budgets[team], spend, now):
                any_alert = True
                print(f"  [{a.severity.upper():8}] {a.message}")
    if not any_alert:
        print("  none")


if __name__ == "__main__":
    main()
