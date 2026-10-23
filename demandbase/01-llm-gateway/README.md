# 01 · LLM gateway (LiteLLM)

> JD: *"The single front door to every model provider we use: keys, routing,
> rate limits, failover, provider quotas. When it's down, every AI feature at
> Demandbase is down."*

A LiteLLM proxy configured the way a platform team runs it: model groups
instead of model names, per-team virtual keys with hard budgets, and two
independent providers with ordered failover.

| File | What it does |
|---|---|
| [`config.yaml`](config.yaml) | Model groups (`chat-small`, `chat-tiny`, `judge`, `embed-small`), per-deployment `rpm`/`tpm` quotas, `order`-based primary/secondary routing, retries, cooldowns, group fallback `chat-small → chat-tiny`, Redis-backed shared state and exact cache, guardrail and callback wiring |
| [`teams.yaml`](teams.yaml) + [`scripts/bootstrap_teams.py`](scripts/bootstrap_teams.py) | Idempotently creates teams and virtual keys with `max_budget`, `budget_duration`, `rpm_limit`, `tpm_limit` and model allowlists |
| [`custom_guardrail.py`](custom_guardrail.py) | LiteLLM adapter for [02-guardrails](../02-guardrails/); policy is picked by the caller's team |
| [`custom_callbacks.py`](custom_callbacks.py) | Success/failure callbacks feeding [04-cost-control](../04-cost-control/) (ClickHouse rows) and [05-llm-observability](../05-llm-observability/) (Prometheus on `:9464`) |
| [`scripts/smoke_test.py`](scripts/smoke_test.py) | Post-deploy check against a live gateway: completion, usage, cache, embeddings, guardrail blocks |
| [`e2e/run_e2e.py`](e2e/run_e2e.py) + [`e2e/mock_ollama.py`](e2e/mock_ollama.py) | Boots the **real** proxy with this config and plugins against fault-injectable mock providers. No models needed; runs in CI in about 20s |
| [`Dockerfile`](Dockerfile) | LiteLLM image with the plugins and config baked in, so a config change ships as a versioned image |

## Routing and failure behaviour

```
request(model=chat-small)
  ├─ deployment order=1  ollama-primary   (rpm 120)
  │     └─ fails → retry (num_retries=2); 3 fails/min → cooldown 30s
  ├─ deployment order=2  ollama-secondary (rpm 60)
  └─ whole group failing → fallback group chat-tiny (smollm2:360m, degraded quality)
```

The e2e test checks this directly: it flips the primary mock to 100% 503s and
asserts every request is then served by `ollama-secondary`, then fails both
and asserts the caller gets a clean 5xx instead of a hang.

## Run

```bash
make e2e                                   # no models
make up && make bootstrap && make smoke    # full stack
```

## Design choices worth defending in an interview

* **Model groups, not model names.** Callers ask for `chat-small`. Moving it to
  a hosted model, or adding a third provider, needs no change from callers.
* **Config is code.** `store_model_in_db: false`: the YAML in git is the source
  of truth, baked into the image and rolled out by Flux. A model change can't be
  made in the UI and silently lost.
* **Hard limits at the gateway, soft limits in costwatch.** The gateway rejects
  requests over `max_budget` (backstop). Costwatch warns on projected overrun
  days earlier (see 04).
* **Shadow pricing** in `model_info`: local models really cost $0, but showback
  needs a comparable number. See [04-cost-control](../04-cost-control/).
