# Runbook: gateway error budget burn / gateway down

**Alerts:** `LLMGatewayErrorBudgetFastBurn`, `LLMGatewayErrorBudgetSlowBurn`, `LLMGatewayDown`
**Impact:** AI features across the product return errors.

## 1. Triage (first 5 minutes)
1. Grafana → *AI Runtime - LLM Gateway* → "Requests/s by model and status". One model group or all?
2. "Served by backend": did traffic shift from `primary` to `secondary`? If so, see [provider-failover.md](provider-failover.md).
3. Gateway pods healthy?
   ```bash
   kubectl -n ai-runtime get pods -l app=llm-gateway
   kubectl -n ai-runtime logs deploy/llm-gateway --since=10m | grep -iE "error|exception" | tail -50
   ```
   Locally: `docker compose logs --since 10m gateway`.
4. Recent change? `flux get kustomizations ai-runtime` and the GitLab deploy log. **A gateway deploy in the last hour is the prime suspect.**

## 2. Mitigate
| Cause | Mitigation |
|---|---|
| Bad gateway release | `git revert` the image bump MR; Flux reconciles (`flux reconcile kustomization ai-runtime --with-source`). Don't `kubectl edit`: Flux will revert you. |
| Provider outage | Confirm fallbacks are working; if the fallback is also failing, temporarily raise `cooldown_time`/lower `allowed_fails` so the router stops hammering the dead provider. |
| Postgres down (keys can't be validated) | LiteLLM caches key auth in memory/Redis for a short while; restore RDS. Check `DATABASE_URL` secret sync (`kubectl -n ai-runtime get externalsecret`). |
| Redis down | Rate limits/cooldowns become per-pod and cache misses rise; requests still flow. Restore ElastiCache; no immediate user impact. |
| Pod OOM / CPU starved | `kubectl top pods`; HPA max reached? Raise `maxReplicas`, check Karpenter is provisioning (`kubectl get nodeclaims`). |

## 3. Verify and close
* `python 01-llm-gateway/scripts/smoke_test.py` passes.
* Error ratio is back under 0.5% on the 5m window.
* Open a postmortem (template: [../postmortems/TEMPLATE.md](../postmortems/TEMPLATE.md)) if the page fired.
