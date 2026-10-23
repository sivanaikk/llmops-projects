# Runbook: gateway latency SLO

**Alert:** `LLMGatewayLatencySLO` (>5% of chat-small slower than 8s for 15m)

1. Is it **queueing** or **generation**? Compare p95 latency with average completion tokens (Tokens/s panel). Longer outputs mean slower requests: check whether a feature started requesting larger `max_tokens`.
2. **Prompt size** panel: p95 prompt tokens jumped? A RAG feature stuffing more context (top_k change) is a common cause. Find the feature in ClickHouse:
   ```sql
   SELECT feature, avg(prompt_tokens), quantile(0.95)(latency_ms)
   FROM llmops.llm_usage WHERE ts > now() - INTERVAL 1 HOUR GROUP BY feature ORDER BY 3 DESC;
   ```
3. Model server saturated? (lab: `OLLAMA_NUM_PARALLEL`; k8s: model-cpu pods CPU at limit). Scale the StatefulSet or add a deployment to the group.
4. Cache hit ratio dropped (Redis restarted / TTL change)? More traffic reaches the models.
