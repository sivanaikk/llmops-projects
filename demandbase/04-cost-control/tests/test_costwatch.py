import asyncio
from datetime import UTC, datetime

import pytest

from costwatch import UsageEvent, price
from costwatch.budgets import Budget, evaluate, project_month_end
from costwatch.callback import BatchWriter, event_from_payload
from costwatch.report import QUERIES, billable_spend, seed_demo
from costwatch.sinks import DuckDBSink


def payload(**over):
    p = {
        "id": "req-1",
        "model": "qwen2.5:0.5b",
        "model_group": "chat-small",
        "custom_llm_provider": "ollama",
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "response_cost": 0.0,
        "cache_hit": False,
        "status": "success",
        "startTime": 100.0,
        "endTime": 100.25,
        "request_tags": ["feature:account-summary"],
        "metadata": {"user_api_key_team_alias": "account-intel", "user_api_key_alias": "acct-intel-prod"},
    }
    p.update(over)
    return p


def test_event_from_payload_uses_shadow_price_for_local_models():
    e = event_from_payload(payload())
    assert e.team == "account-intel"
    assert e.feature == "account-summary"
    assert e.provider_model == "ollama/qwen2.5:0.5b"
    assert e.cost_usd == pytest.approx(price("chat-small", 1000, 500))
    assert e.latency_ms == pytest.approx(250)


def test_event_from_payload_prefers_gateway_cost_and_requester_feature():
    e = event_from_payload(payload(response_cost=0.5, metadata={"requester_metadata": {"feature": "email-draft"}}))
    assert e.cost_usd == 0.5 and e.feature == "email-draft" and e.team == "unattributed"


def test_duckdb_showback_queries_run():
    sink = DuckDBSink()
    seed_demo(sink, n=200)
    for sql in QUERIES.values():
        assert sink.query(sql), sql
    spend = billable_spend(sink)
    assert set(spend) <= {"account-intel", "internal-tools", "data-science"}


def test_cache_hits_excluded_from_billable_spend():
    sink = DuckDBSink()
    common = dict(team="t", model="chat-small", provider_model="ollama/x", prompt_tokens=10, completion_tokens=10)
    sink.write([UsageEvent(request_id="a", cost_usd=1.0, **common), UsageEvent(request_id="b", cost_usd=2.0, cache_hit=True, **common)])
    assert billable_spend(sink) == {"t": 1.0}


def test_projection_and_alerts():
    now = datetime(2026, 10, 11, 0, 0, tzinfo=UTC)  # 10 days elapsed of 31
    assert project_month_end(10.0, now) == pytest.approx(31.0)
    alerts = evaluate(Budget("t", monthly_usd=20), spend_to_date=10.0, now=now)
    sev = {a.severity for a in alerts}
    assert "info" in sev  # crossed 50%
    assert any("on pace" in a.message for a in alerts)


def test_no_alerts_when_under_budget():
    now = datetime(2026, 10, 16, tzinfo=UTC)
    assert evaluate(Budget("t", monthly_usd=100), spend_to_date=5.0, now=now) == []


class FailingSink:
    def write(self, events):
        raise RuntimeError("clickhouse down")


class ListSink:
    def __init__(self):
        self.rows = []

    def write(self, events):
        self.rows.extend(events)


def test_batch_writer_dead_letters_on_failure():
    dl = ListSink()
    w = BatchWriter(FailingSink(), batch_size=2, dead_letter=dl)
    ev = event_from_payload(payload())

    async def go():
        await w.add(ev)
        await w.add(ev)

    asyncio.run(go())
    assert len(dl.rows) == 2
