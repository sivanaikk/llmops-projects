# Learn: building a feature *on* an AI platform (RAG)

**You'll be able to:** build a small RAG feature that uses platform services
(gateway, cache, tracing) instead of reinventing them; chunk and retrieve with
entity-aware scoring; version prompts; trace one question end to end.
**Time:** ~1.5 h · **Needs:** Python (gateway for real answers)

---

## 1. The problem

The platform (modules 01–06) only matters if product features can use it
easily. This module plays the product team: a B2B "account intelligence" Q&A over
notes for six fictional companies. It's also the workload the evals and dashboards run against.

## 2. Concepts

```
question ─► retrieve (embed via gateway, cosine + entity boost) ─► semantic cache (tenant + prompt scope)
         ─► prompt vN + top-k chunks ─► gateway chat (team key, feature tag, traceparent) ─► answer + sources
```

| Concern | Provided by |
|---|---|
| model access, budget, guardrails | the gateway: the app sends a team key and `metadata.feature` |
| repeated questions | semcache, scoped to (team, model, system prompt) |
| debugging | llmobs spans: `account_intel.answer` → `retrieve` → `chat chat-small` |
| quality gate | evalkit, which treats `AccountAssistant.answer` as the system under test |

**Chunking:** one chunk per `## section`, **prefixed with the account name**, so a
question about "Northwind's buyer" can't match Acme's buying-group section.

**Entity boost:** small embedding models are weak at proper nouns, so chunks whose account
name appears in the question get +0.25. Crude, explicit and testable, and a good example of
a domain heuristic you'd later measure with `retrieval_hit`.

**Prompt versions are deploys:** `prompts.py` holds `v1` and `v2`; switching is a config change
that must pass the eval gate.

## 3. Walkthrough

```bash
pytest 07-account-rag-app -q        # runs on a fake gateway + hashing embedder, no model
```

Read [`tests/test_account_rag.py`](tests/test_account_rag.py) `FakeGateway`: it echoes which source
was retrieved, so tests can check retrieval without a model. Then [`account_rag/app.py`](account_rag/app.py)
`answer`: retrieval, then cache lookup, then the model call, all inside spans.

With the gateway running: `python -m account_rag "Who is the economic buyer at Northwind Robotics?"`.

## 4. Exercises (open-ended)

1. **Measure the entity boost.** Run the evals ([06](../06-evals-harness/LEARN.md)) with the boost at 0, 0.1
   and 0.25. Plot `retrieval_hit`. Is 0.25 justified?
2. **Hybrid retrieval:** add BM25 keyword scoring and combine it with the cosine score. Which questions improve?
3. **Citations:** prompt v2 asks for `[source-id]`. Write a scorer that checks the cited source is one that was retrieved.

## 5. Check yourself

<details><summary>1. Why prefix each chunk with the account name?</summary>

Sections like "Buying group" are nearly identical across accounts. Without the name, a question about one
account can retrieve another account's section, which is a retrieval bug that looks like a hallucination.
</details>

<details><summary>2. Why does the app send `metadata.feature` on every call?</summary>

So spend, latency and errors can be attributed to this feature, not just the team (see [04-cost-control](../04-cost-control/LEARN.md)).
</details>

## 6. In the interview

* "Describe a RAG system you built." The pipeline, chunking decisions, entity boost, prompt versions behind an eval gate,
  and the split between retrieval_hit and fact_recall when debugging.
