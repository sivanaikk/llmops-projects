# Learn: the LLM gateway (one front door for every model)

**You'll be able to:** explain why a platform puts a gateway in front of every
model; configure model groups, ordered failover, retries, cooldowns and
fallbacks in LiteLLM; issue team keys with budgets; prove failover works with
fault-injecting mock providers.
**Time:** ~2 h · **Needs:** Python (`pip install 'litellm[proxy]'`); Docker optional

---

## 1. The problem

Without a gateway, every product team calls providers directly: each with its
own keys, retry logic, rate-limit handling and cost tracking. When a provider has
an outage, ten teams discover it separately, and nobody can say what AI costs per
feature. A gateway centralises the *cross-cutting* concerns so product teams only write product.

## 2. Concepts

```
caller ──► virtual key (team) ──► guardrails ──► cache ──► router ──► provider deployment
           budget, rpm/tpm        PII, injection   exact     order, retries,
                                                             cooldown, fallback
```

**Model groups, not model names.** Callers ask for `chat-small`, never
`ollama/qwen2.5:0.5b` or `gpt-4o-mini`. Moving a group to another provider is a
config change; no caller changes.

**Routing and failure handling** ([`config.yaml`](config.yaml)):

```
request(model=chat-small)
  ├─ deployment order=1  ollama-primary   (rpm 120)   ← preferred
  │    └─ error → retry (num_retries=2); 3 fails/min → cooldown 30s
  ├─ deployment order=2  ollama-secondary (rpm 60)    ← used when order=1 is cooling down
  └─ whole group failing → fallback group chat-tiny (smaller model, degraded quality)
```

| Knob | Protects against |
|---|---|
| `rpm`/`tpm` per deployment | exceeding a provider's quota (429 storms) |
| `allowed_fails` + `cooldown_time` | hammering a provider that is down |
| `fallbacks` | total outage of a model group (at a quality cost: tell product owners!) |
| Redis for router state | each replica cooling down independently and disagreeing |
| team `max_budget` + key `rpm_limit` | one team or one runaway script using everyone's capacity |

**Config is code:** `store_model_in_db: false`, so the YAML in git is the truth. It is baked into
the image and rolled out by Flux ([08-platform-infra](../08-platform-infra/LEARN.md)).

## 3. Walkthrough: prove failover with no models

```bash
pip install 'litellm[proxy]'
python 01-llm-gateway/e2e/run_e2e.py
```

This boots **the real LiteLLM proxy with this config and plugins** against two mock
Ollama servers ([`e2e/mock_ollama.py`](e2e/mock_ollama.py)) that can be told to fail. Real output:

```
[PASS] chat-small routes to primary
[PASS] embeddings
[PASS] guardrail blocks injection (400)
[PASS] PII redacted before reaching provider  ([ollama-primary:qwen2.5:0.5b] You asked: please email <EMAIL_7db00ed2> the deck)
[PASS] exact response cache  (0.03s)
[PASS] failover to secondary when primary is down
[PASS] total outage returns a clean 5xx, not a hang  (503)
[PASS] prometheus requests counter
[PASS] served_by shows both backends
...
ALL PASSED
```

Read [`e2e/run_e2e.py`](e2e/run_e2e.py) `main` top to bottom: it is a script of the gateway's promises.
Notice how the mock echoes the prompt, which is how the test *proves* the PII was redacted before reaching the provider.

Full stack with real small models: `make up && make bootstrap && make smoke` (Docker, ~2 GB of models).

## 4. Exercises (open-ended)

1. **Add a third provider** to `config.yaml`: a `gpt-4o-mini` deployment as `order: 3` for `chat-small`
   (you don't need a key to reason about it). What `model_info` costs would you set, and how would showback change?
2. **Extend the e2e:** make the mock primary *slow* (`/admin/latency?seconds=5`) instead of failing.
   What should the gateway do, and which config knob controls it? Write the check.
3. Find the single point of failure the game day in [09-sre](../09-sre/LEARN.md) talks about
   (hint: `embed-small`), fix it in config, and add an e2e check.

## 5. Check yourself

<details><summary>1. Why prefer `order`-based failover over load-balancing both providers equally?</summary>

The primary may be cheaper, faster or contractually preferred, and keeping the secondary warm but lightly
used preserves its quota for when you need it. Equal balancing is right when both are equivalent and you want
to spread load.
</details>

<details><summary>2. Fallback to `chat-tiny` kept availability at 100% during an outage. Any problem?</summary>

Quality dropped silently. Availability SLOs don't see it, which is why there's a `LLMDegradedModelServing`
alert and why product owners must be told.
</details>

<details><summary>3. What does the gateway return when *everything* is down, and why does it matter?</summary>

A clean 5xx quickly (the e2e test asserts 503), not a hang. Callers can then fail fast or show a
degraded experience instead of tying up threads until their own timeouts fire.
</details>

## 6. In the interview

* "Why a gateway?" Centralise keys, quotas, retries/failover, guardrails, caching, cost attribution and
  observability; product teams only pick a model group.
* "How do you test failover?" The e2e: a real proxy, mock providers with fault injection, run in CI on every config change.

## Go further
* LiteLLM docs: Router (routing strategies, fallbacks, cooldowns), Virtual Keys, Budgets
