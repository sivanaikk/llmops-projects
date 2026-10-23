# Learn: response and semantic caching (and how it leaks data)

**You'll be able to:** choose between exact and semantic caching; scope a cache
so it can't leak across tenants or prompt versions; decide what is cacheable;
pick a similarity threshold from measured hit and false-hit rates.
**Time:** ~1.5 h · **Needs:** Python (gateway for real embeddings, optional)

---

## 1. The problem

Many LLM requests repeat ("What's Acme's intent score?"). Caching saves latency
and money. A *semantic* cache also matches paraphrases. That's where it gets
dangerous: "similar" questions can need different answers, or belong to different customers.

## 2. Concepts

| | Exact cache (gateway, Redis) | Semantic cache (app, embeddings) |
|---|---|---|
| key | hash(model, messages, params) | embedding of the question |
| hit when | identical request | cosine similarity ≥ threshold |
| risk | stale answers | **wrong answers**, **cross-tenant leaks** |

**Scope = (tenant, model, system-prompt hash).** A semantic hit must never return
another tenant's answer, or an answer produced under a different prompt version.

**Not everything is cacheable:** `temperature > 0.2` (the caller *wants* variety),
tool calls, streaming.

**The threshold is a product decision made from data:** a hit rate on true paraphrases
vs a **false-hit** rate on near-misses ("Northwind's intent score" vs "Acme's intent
score"). For customer-facing answers, the false-hit budget is ~0.

## 3. Walkthrough

```bash
python 03-semantic-cache/bench/benchmark.py            # offline lexical embedder
python 03-semantic-cache/bench/benchmark.py --gateway  # all-minilm via the gateway (stack running)
```

Real output with the offline lexical embedder (excerpt):

```
threshold  hit_rate  false_hit
    0.500      0.75       1.00
    0.750      0.25       0.38
    0.825      0.00       0.12
    0.900      0.00       0.00
```

A word-hashing embedder **can't separate** paraphrases from near-misses: by the
time false hits reach 0, so do real hits. That's the argument for a real embedding
model, measured on *your* labelled pairs in [`bench/pairs.jsonl`](bench/pairs.jsonl), before turning the cache on.

Read [`semcache/cache.py`](semcache/cache.py): `scope`, `cacheable`, then `lookup` (exact first, then
semantic; expired entries are evicted during the scan).

## 4. Exercises

```bash
make check EX=02     # a working cache with two production bugs: find and fix them
```

Challenges:
1. Run the benchmark with `--gateway` (all-minilm). What threshold gives 0 false hits, and what hit rate do you keep?
2. Add 10 near-miss pairs from your own domain to `pairs.jsonl`. Do they change the recommended threshold?
3. The linear scan is O(n) per lookup. At what size would you move to an ANN index (Redis/Qdrant HNSW),
   and what new failure mode does approximate search add?

## 5. Break it

```bash
make break-it ID=cache-tenant-leak
make break-it ID=cache-no-ttl
make break-it ID=cache-caches-sampled-answers
```

## 6. Check yourself

<details><summary>1. Why is the exact cache at the gateway but the semantic cache in the app?</summary>

Exact keys already include everything that defines the answer, so they're safe for every caller.
Semantic matching needs product knowledge (tenant, prompt version, freshness, acceptable false-hit rate)
that only the feature owner has.
</details>

<details><summary>2. Hit rate went from 5% to 40% after lowering the threshold. Good?</summary>

Only if the false-hit rate stayed within budget. Check it on the labelled pairs. A higher hit rate made
of wrong answers is a quality incident that looks like a cost win.
</details>

<details><summary>3. How do cache hits show up in cost reporting?</summary>

Logged at the price they *would* have cost and excluded from billable spend, so "saved by caching"
is directly comparable to spend (see [04-cost-control](../04-cost-control/LEARN.md)).
</details>

## 7. In the interview

* "Would you add semantic caching to a customer-facing feature?" Yes, if scoped per tenant and prompt
  version, with a threshold chosen on labelled near-misses and a false-hit budget near zero. Otherwise exact caching only.

## Go further
* GPTCache and Redis semantic cache docs; papers on embedding-based caching for LLMs
