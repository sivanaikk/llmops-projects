"""Where usage events land.

ClickHouse is the production sink (columnar, cheap to keep a year of per-call
rows, fast GROUP BY for showback). DuckDB uses the same SQL dialect closely
enough to run the showback queries locally and in tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

import httpx

from .events import UsageEvent

COLUMNS = [
    "ts", "request_id", "team", "feature", "api_key_alias", "model", "provider_model",
    "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd", "cache_hit", "status", "latency_ms",
]

DUCKDB_DDL = """
CREATE TABLE IF NOT EXISTS llm_usage (
    ts TIMESTAMP, request_id VARCHAR, team VARCHAR, feature VARCHAR, api_key_alias VARCHAR,
    model VARCHAR, provider_model VARCHAR, prompt_tokens BIGINT, completion_tokens BIGINT,
    total_tokens BIGINT, cost_usd DOUBLE, cache_hit BOOLEAN, status VARCHAR, latency_ms DOUBLE
)
"""


class Sink(Protocol):
    def write(self, events: list[UsageEvent]) -> None: ...

    def query(self, sql: str) -> list[dict]: ...


class DuckDBSink:
    def __init__(self, path: str = ":memory:"):
        import duckdb

        self.con = duckdb.connect(path)
        self.con.execute(DUCKDB_DDL)

    def write(self, events: list[UsageEvent]) -> None:
        if not events:
            return
        rows = [[e.as_row()[c] for c in COLUMNS] for e in events]
        self.con.executemany(f"INSERT INTO llm_usage ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})", rows)

    def query(self, sql: str) -> list[dict]:
        cur = self.con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


class ClickHouseSink:
    """Minimal HTTP-interface client; no driver dependency needed."""

    def __init__(self, url: str | None = None, database: str = "llmops", user: str | None = None, password: str | None = None):
        self.url = (url or os.getenv("CLICKHOUSE_URL", "http://localhost:8123")).rstrip("/")
        self.database = database
        self.auth = (user or os.getenv("CLICKHOUSE_USER", "default"), password or os.getenv("CLICKHOUSE_PASSWORD", ""))
        self.client = httpx.Client(timeout=10)

    def write(self, events: list[UsageEvent]) -> None:
        if not events:
            return
        body = "\n".join(json.dumps({c: e.as_row()[c] for c in COLUMNS}) for e in events)
        r = self.client.post(
            self.url,
            params={"query": f"INSERT INTO {self.database}.llm_usage FORMAT JSONEachRow", "date_time_input_format": "best_effort"},
            content=body,
            auth=self.auth,
        )
        r.raise_for_status()

    def query(self, sql: str) -> list[dict]:
        r = self.client.post(
            self.url, params={"database": self.database, "default_format": "JSONEachRow"}, content=sql, auth=self.auth
        )
        r.raise_for_status()
        return [json.loads(line) for line in r.text.splitlines() if line]


class JsonlSink:
    """Append-only file sink; handy as a dead-letter fallback when ClickHouse is down."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write(self, events: list[UsageEvent]) -> None:
        with self.path.open("a") as f:
            for e in events:
                f.write(json.dumps(e.as_row()) + "\n")

    def query(self, sql: str) -> list[dict]:
        raise NotImplementedError("load the file into DuckDB to query it")


def from_env() -> Sink:
    kind = os.getenv("COSTWATCH_SINK", "duckdb")
    if kind == "clickhouse":
        return ClickHouseSink()
    if kind == "jsonl":
        return JsonlSink(os.getenv("COSTWATCH_JSONL", "usage.jsonl"))
    return DuckDBSink(os.getenv("COSTWATCH_DUCKDB", "usage.duckdb"))
