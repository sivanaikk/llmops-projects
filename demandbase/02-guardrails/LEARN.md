# Learn: guardrails at the gateway (PII, injection, policy)

**You'll be able to:** detect structured PII with regex *plus checksums*;
explain redaction vs blocking and stable pseudonyms; score prompt-injection
attempts explainably; apply different policies per team.
**Time:** ~1.5 h · **Needs:** Python only

---

## 1. The problem

Every prompt is a potential data leak (customer PII sent to a third-party model)
and a potential attack (instructions hidden in user or tool content). Checks have
to run on **every request**, so they must be fast (microseconds), deterministic,
and explainable in an incident review.

## 2. Concepts

**Regex finds candidates; checksums confirm them.** "13 to 19 digits" matches every
card number, and also order IDs, timestamps and phone numbers.

| Entity | Pattern | Validator |
|---|---|---|
| credit card | 13–19 digits | **Luhn** |
| Aadhaar (India) | 12 digits starting 2–9 | **Verhoeff** |
| IBAN | 2 letters + 2 digits + up to 30 alphanumerics | **mod-97** (exercise A-01) |

This lab shipped *without* the Aadhaar checksum, and the learning walkthrough found
it: "order 1234 5678 9012 3456 shipped" got part of the order number redacted as an
Aadhaar number. Adding Verhoeff fixed it, and a regression test now guards it.

**Redact vs block.** Contact details are redacted to **stable pseudonyms**
(`<EMAIL_758e0983>`): the same address maps to the same token within a request, so the
model can still reason about "the same person". High-risk identifiers (cards, SSNs,
cloud keys) are blocked outright.

**Injection scoring** ([`guardkit/injection.py`](guardkit/injection.py)): weighted signals
combined with a noisy-OR, `1 − Π(1 − wᵢ)`. Several weak signals add up, the score never
exceeds 1, and the matched signal names explain *why* something was blocked.

**Only check what users and tools send.** The system prompt is ours; tool output is
attacker-controllable, so it is checked too.

## 3. Walkthrough

```python
# from demandbase/:  PYTHONPATH=02-guardrails python
from guardkit import load_policies, check_input
p = load_policies("02-guardrails/policies.yaml")
check_input("Email the CFO at jane.doe@acme.com about Q3", p["account-intel"], salt="demo")
```

Real output for five inputs:

```
account-intel   redact  ['pii_redacted:EMAIL']                    -> 'Email the CFO at <EMAIL_758e0983> about Q3'
account-intel   block   ['prompt_injection:ignore_previous,reveal_system_prompt']
default         block   ['pii_blocked:CREDIT_CARD']               -> 'my card is 4111 1111 1111 1111'
default         allow   []                                         -> 'order 1234 5678 9012 3456 shipped'
internal-tools  allow   []                                         -> 'ping ops@demandbase.example'
```

Same email, different teams, different results: that's [`policies.yaml`](policies.yaml).
Read [`guardkit/pii.py`](guardkit/pii.py) → [`policy.py`](guardkit/policy.py) `check_input` (note the order:
length, topics, injection, then PII) → [`gateway.py`](guardkit/gateway.py) → the LiteLLM adapter
[`../01-llm-gateway/custom_guardrail.py`](../01-llm-gateway/custom_guardrail.py).

## 4. Exercises

```bash
make check EX=01     # Luhn, IBAN mod-97, find IBANs in free text
```

Challenges:
1. Add your exercise's IBAN detection to `guardkit/pii.py` as a real rule, with tests.
2. Write three prompt-injection attempts that **evade** the current signals (e.g. obfuscation,
   another language, instructions inside a fake tool result). This is how red-teaming finds gaps.
   Then decide: more regexes, or a small classifier behind the same `score()` interface?
3. Output guardrails: the model may *generate* PII it saw in context. Write a test for `check_output`
   with a policy that blocks instead of redacting.

## 5. Break it

```bash
make break-it ID=pii-no-luhn
make break-it ID=injection-scoring-disabled
make break-it ID=guardrail-checks-system-prompt
```

## 6. Check yourself

<details><summary>1. Why not use an LLM to detect PII on every request?</summary>

Latency and cost: a second model call per request, plus non-determinism. A model can sit *behind* the
fast checks for ambiguous cases (names, addresses), but structured identifiers are best caught by
regex + checksum.
</details>

<details><summary>2. Why salt the pseudonyms per request?</summary>

So tokens are consistent within a request but can't be joined across requests or users to re-identify someone.
</details>

<details><summary>3. A guardrail spike: 50 blocks a minute for one team. Attack or bug?</summary>

Check whether the policy or guardkit changed recently (revert first if so), then group the blocks by key and
reason in the logs. See [09-sre/runbooks/guardrail-spike.md](../09-sre/runbooks/guardrail-spike.md).
</details>

## 7. In the interview

* "How do you handle PII with third-party LLMs?" Redact or block at the gateway; checksums to keep false
  positives down; pseudonyms; per-team policy; output checks too; the Aadhaar false positive as a story.
* "How do you defend against prompt injection?" Layers: input scoring at the gateway, least-privilege tools,
  code-level guards (Track B module 01). No single filter is enough.

## Go further
* OWASP Top 10 for LLM Applications (LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure)
* Microsoft Presidio (model-assisted PII detection)
