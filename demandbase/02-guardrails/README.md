# 02 · Guardrails (`guardkit`)

> JD: *"input/output safety, PII handling, and policy enforcement at the gateway"*

Fast, explainable guardrails that run inline on every gateway request.

| Check | Where | Behaviour |
|---|---|---|
| PII detection: email, phone, credit card (Luhn-validated), US SSN, Indian PAN/Aadhaar, IPv4, AWS keys, `sk-` API keys | input + output | **redact** to stable per-request pseudonyms (`<EMAIL_1a2b3c4d>`) or **block** for high-risk entities |
| Prompt injection / jailbreak heuristics (noisy-OR over weighted signals) | user/tool messages | block over a per-team threshold; matched signal names are logged for incident review |
| Denied topics, max input length | input | block |

Policies are per team in [`policies.yaml`](policies.yaml), selected by the
caller's LiteLLM team alias: the customer-facing `account-intel` feature is
strict; `internal-tools` allows contact details but still blocks secrets.

```
guardkit/
  pii.py        detect + redact, salted pseudonyms
  injection.py  weighted signal scoring
  policy.py     Policy, check_input / check_output → Decision(allow|redact|block)
  gateway.py    applies a policy to OpenAI-format messages (no LiteLLM import → unit-testable)
```

The LiteLLM adapter is [`../01-llm-gateway/custom_guardrail.py`](../01-llm-gateway/custom_guardrail.py).
Blocked requests return `400 {"error": "guardrail_blocked", "reasons": [...]}`
and increment `airt_guardrail_blocks_total{team,reason}` (alerted on in 05).

**Why regex/heuristics rather than a model?** Latency: microseconds versus a
second model call on every request. They are also deterministic and easy to
explain in a postmortem. A classifier (e.g. Presidio or a small injection
model) can sit behind the same `Decision` interface for teams that need it.

```bash
make test   # 18 guardrail tests
```
