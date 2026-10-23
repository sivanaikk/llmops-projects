# 03 · Response and semantic caching (`semcache`)

> JD: *"Response and semantic caching to cut latency and redundant spend"*

Two layers:

1. **Exact cache at the gateway**: LiteLLM + Redis (`cache_params` in
   [`01-llm-gateway/config.yaml`](../01-llm-gateway/config.yaml)). Safe by
   construction: the key covers model, messages and params. Verified in the e2e test.
2. **Semantic cache in the app layer**: [`semcache/cache.py`](semcache/cache.py).
   Embeds the question and returns a cached answer when a previous question
   was similar enough.

Semantic caching is where teams get burned, so the implementation is explicit about:

* **Scope**: entries are partitioned by `(tenant, model, system-prompt hash)`.
  A semantic hit must never return one tenant's answer to another, or an answer
  produced under a different prompt version.
* **What's cacheable**: no `temperature > 0.2`, tools or streaming.
* **TTL and LRU bounds**: account facts go stale.
* **Threshold from data**: [`bench/benchmark.py`](bench/benchmark.py) sweeps the
  threshold over labelled pairs: paraphrases that *should* hit, plus
  near-misses that must *not* (same question, different account; "CTO" vs
  "CFO"; "last month" vs "last year"). It reports hit rate against false-hit rate.

```bash
make cache-bench            # offline hashing embedder
make cache-bench GATEWAY=1  # all-minilm through the gateway
```

The offline lexical embedder can't hit a single paraphrase without also
false-hitting near-misses (at threshold 0.9: 0% hits, 0% false hits; lower
thresholds produce false hits before useful hits). That is the argument for a
real embedding model, *and* for keeping a false-hit budget of ~0 for
customer-facing answers: "Northwind's intent score" and "Acme's intent score"
are lexically almost the same question.
