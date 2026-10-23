# Runbook: guardrail block spike

**Alert:** `GuardrailBlockSpike`

1. Reason label tells you which check: `prompt_injection`, `pii_blocked`, `denied_topic`, `input_too_long`.
2. **Policy rollout?** Did `02-guardrails/policies.yaml` or `guardkit` change recently? A threshold tweak can block legitimate traffic: revert first, investigate after.
3. **Attack?** Loki: `{service="gateway"} |= "guardkit blocked"` and group by key alias. One key / end user responsible → rate-limit or disable that key.
4. **Legitimate content tripping a rule** (e.g. support tickets with card numbers): give that team its own policy entry rather than loosening `default`.
5. Never "fix" a spike by turning guardrails off globally.
