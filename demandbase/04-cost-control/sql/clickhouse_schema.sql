-- Per-call usage rows written by costwatch.callback (LiteLLM success/failure hook).
CREATE DATABASE IF NOT EXISTS llmops;

CREATE TABLE IF NOT EXISTS llmops.llm_usage
(
    ts                DateTime64(3, 'UTC'),
    request_id        String,
    team              LowCardinality(String),
    feature           LowCardinality(String),
    api_key_alias     LowCardinality(String),
    model             LowCardinality(String),
    provider_model    LowCardinality(String),
    prompt_tokens     UInt32,
    completion_tokens UInt32,
    total_tokens      UInt32,
    cost_usd          Float64,
    cache_hit         Bool,
    status            LowCardinality(String),
    latency_ms        Float32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (team, model, ts)
TTL toDateTime(ts) + INTERVAL 13 MONTH;

-- Daily rollup kept forever for trend lines and finance exports; raw rows age out.
CREATE TABLE IF NOT EXISTS llmops.llm_usage_daily
(
    day          Date,
    team         LowCardinality(String),
    feature      LowCardinality(String),
    model        LowCardinality(String),
    calls        UInt64,
    cache_hits   UInt64,
    tokens       UInt64,
    cost_usd     Float64
)
ENGINE = SummingMergeTree
ORDER BY (day, team, feature, model);

CREATE MATERIALIZED VIEW IF NOT EXISTS llmops.llm_usage_daily_mv TO llmops.llm_usage_daily AS
SELECT
    toDate(ts) AS day, team, feature, model,
    count() AS calls,
    countIf(cache_hit) AS cache_hits,
    sum(total_tokens) AS tokens,
    sumIf(cost_usd, NOT cache_hit) AS cost_usd
FROM llmops.llm_usage
GROUP BY day, team, feature, model;
