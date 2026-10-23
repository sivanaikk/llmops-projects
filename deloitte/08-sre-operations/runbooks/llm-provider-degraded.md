# Runbook: LLM provider degraded

**Signals:** `llm_unavailable` outcomes, `agent_llm_errors_total{retryable="true"}`, `AgentLatencyHigh`

1. At the gateway (if used): which deployment is failing, and are fallbacks serving?
   See `demandbase/09-sre/runbooks/provider-failover.md` for the gateway side.
2. Provider quota (429s)? Azure OpenAI TPM quota is set in `openai.tf` (`capacity`):
   raise it, or shed low-priority traffic at the gateway.
3. Self-hosted small model (Ollama on AKS): pod CPU-throttled? OOMKilled? Node evicted (spot)?
4. While degraded, lower `AGENT_MAX_STEPS` to reduce model calls per request.
5. Chaos experiments `llm-latency`, `llm-outage` and `llm-stall` rehearse exactly this. If behaviour
   differs from their hypotheses, that's a finding for the postmortem.
