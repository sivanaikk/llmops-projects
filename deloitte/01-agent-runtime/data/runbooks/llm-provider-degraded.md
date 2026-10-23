# Runbook: LLM provider degraded
Tags: llm, model, provider, azure openai, bedrock, rate limit, 429
1. Confirm at the gateway: rising 429/5xx from one provider deployment.
2. Gateway fallbacks should shift traffic; confirm the fallback deployment has quota.
3. If quality-degraded fallback models are serving, notify product owners.
4. Lower agent max_steps temporarily to cut model calls per request.
