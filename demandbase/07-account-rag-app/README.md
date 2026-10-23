# 07 · Account Intel: a RAG feature on the runtime

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"you need to have built something with these tools: an agent, a RAG
> pipeline, an internal tool, and to have used evals or experiments to decide
> whether it was any good."*

A small B2B "account intelligence" assistant over notes for six **fictional**
companies (intent score, journey stage, buying group, notes), the kind of
feature a Demandbase product team would build. It's the workload that the
rest of the runtime is exercised with.

It only uses platform pieces, as a product team would:

| Concern | Provided by |
|---|---|
| model access, team key, budget, guardrails | gateway (01) via [`gateway.py`](account_rag/gateway.py): sends `metadata.feature` for cost attribution and `traceparent` for tracing |
| tenant-scoped semantic cache | [03-semantic-cache](../03-semantic-cache/) |
| spans for retrieve → LLM call | [05-llm-observability](../05-llm-observability/) |
| quality gate on prompt changes | [06-evals-harness](../06-evals-harness/) |

```
account_rag/
  index.py     chunk per "## section", prefix with account name, cosine + entity boost
  prompts.py   versioned prompts (v1 baseline, v2 grounded + abstain + cite)
  app.py       retrieve → cache lookup → chat → cache store, all traced
  server.py    FastAPI /ask, /healthz, /cache/stats
```

```bash
python -m account_rag "Who is the economic buyer at Northwind Robotics?"   # needs the gateway
docker compose up account-intel   # http://localhost:8080/docs
```
