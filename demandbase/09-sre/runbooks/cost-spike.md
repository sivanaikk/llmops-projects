# Runbook: LLM spend spike

**Alerts:** `LLMSpendSpike` (Prometheus), costwatch budget alerts (`python -m costwatch.report`)

1. Which team, model and feature?
   ```sql
   SELECT team, feature, model, count() calls, sum(cost_usd) usd, avg(prompt_tokens) avg_in
   FROM llmops.llm_usage WHERE ts > now() - INTERVAL 2 HOUR
   GROUP BY team, feature, model ORDER BY usd DESC LIMIT 10;
   ```
2. Classify:
   * **More calls** at the same size → traffic growth, a retry loop, or an agent stuck in a loop (look for one `api_key_alias` dominating).
   * **Bigger prompts** → context stuffing / prompt template change.
   * **Model mix shift** → someone switched to a pricier model group.
   * **Cache hit ratio drop** → previously cached traffic now billed.
3. Mitigate without breaking the feature:
   * Runaway key: lower that key's `rpm_limit`/`max_budget` (`/key/update`): instant and reversible.
   * Team-wide: the hard `max_budget` in `01-llm-gateway/teams.yaml` is the backstop. Raising it is a conscious decision by the owning team's manager.
4. Follow up with the owning team; record the cause in the weekly showback.
