# Learn: LLM cost attribution and FinOps

**You'll be able to:** attribute every model call to a team, feature and model;
price self-hosted usage with shadow prices; build showback reports; combine hard
budgets with early-warning projections.
**Time:** ~1.5 h · **Needs:** Python (DuckDB; ClickHouse in the full stack)

---

## 1. The problem

LLM spend is the line item that quietly triples: a new feature, a longer prompt,
a retry loop. Finance sees one number per provider. Engineering needs *who, what
feature, which model, and what changed*, and needs it before the month ends.

## 2. Concepts

**One row per call** ([`costwatch/events.py`](costwatch/events.py)): team (from the virtual key),
feature (from request metadata), model group *and* the deployment that served it,
tokens, cost, cache hit, latency.

**Shadow pricing.** Self-hosted models cost $0 per token, but not $0 in GPUs.
Attach a reference price ([`costwatch/pricing.py`](costwatch/pricing.py)) so showback,
budgets and anomaly alerts work, and so "move to a hosted model" can be costed.

**Two kinds of budget:**

| | Hard | Soft |
|---|---|---|
| where | LiteLLM team/key `max_budget` | `budgets.yaml` + projection + `LLMSpendSpike` alert |
| when it acts | spend reaches the limit | projected month-end exceeds the budget |
| effect | requests rejected | warning to the owning team, days earlier |

**Projection:** `projected = spend_so_far / elapsed_days × days_in_month` (with a minimum elapsed
time so the first hour doesn't extrapolate wildly).

**Cache savings:** hits are logged at what they would have cost and excluded from billable spend.

**Storage:** ClickHouse MergeTree partitioned by month with a 13-month TTL, plus a
`SummingMergeTree` daily rollup kept forever ([`sql/clickhouse_schema.sql`](sql/clickhouse_schema.sql)).

## 3. Walkthrough

```bash
cd 04-cost-control && python -m costwatch.report --demo
```

Real output (synthetic traffic; amounts depend on today's date):

```
== by_team ==
  team            calls  tokens  cost_usd
  account-intel   1086   991848  17.6964
  internal-tools  606    582891  13.1569
  data-science    308    280249  13.1429
...
== budget alerts ==
  [INFO    ] internal-tools has used 70% of its $15.00 monthly LLM budget
  [WARNING ] internal-tools is on pace to spend ... vs $15.00 budget
  [CRITICAL] data-science has used 110% of its $10.00 monthly LLM budget
```

Read [`costwatch/callback.py`](costwatch/callback.py) `event_from_payload` (where team and feature come from)
and `BatchWriter` (batched, off the event loop, dead-lettered on failure: billing must never fail a user request).

## 4. Exercises

```bash
make check EX=04     # shadow price, month-end projection, alert levels
```

Challenges:
1. Add a `cost per successful answer` metric: spend / (calls − failures − cache hits). Why can it go *up*
   when total spend goes down?
2. Write the ClickHouse query for "top 5 features by week-over-week spend growth".
3. Chargeback vs showback: what would change in the data model to actually bill teams?

## 5. Break it

```bash
make break-it ID=cost-bills-cache-hits
make break-it ID=cost-no-shadow-price
make break-it ID=cost-sink-failure-fails-requests
```

## 6. Check yourself

<details><summary>1. Why tag the feature, not just the team?</summary>

Teams own several features. "account-intel spent 3x more" isn't actionable; "the email-draft feature's
prompt grew from 800 to 3,000 tokens" is.
</details>

<details><summary>2. Why is the hard budget alone not enough?</summary>

It acts when the money is gone, and the feature then fails for users. The projection warns while there's time
to fix the cause (or consciously raise the budget).
</details>

<details><summary>3. ClickHouse is down. What happens to user requests?</summary>

Nothing: writes are batched off the request path, and a failed batch goes to a dead-letter file for replay.
</details>

## 7. In the interview

* "How do you control LLM spend?" Attribution per team and feature, shadow prices for self-hosted, hard
  limits at the gateway, projections and anomaly alerts, cache savings in the same report.

## Go further
* FinOps Foundation: "FinOps for AI" working-group material
