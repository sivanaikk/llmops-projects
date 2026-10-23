# 01 · Agent runtime (`agentops`)

> JD: *"Operate AI and agentic workloads reliably"*, *"AI failure modes"*,
> *"code instrumentation"*.

A tool-using **incident-desk agent** (an SRE assistant over a fictional
service catalogue and runbooks), built so it can't fail in the ways agents
usually fail in production. It runs on `qwen2.5:1.5b` (or `0.5b`) through Ollama's
OpenAI-compatible API, or through any gateway.

| Failure mode | Bound | Where |
|---|---|---|
| loops / too many model calls | `max_steps`, loop detection on repeated identical tool calls | `agent.py` |
| runaway spend | per-run `max_cost_usd` and `max_total_tokens` (shadow-priced for local models) | `agent.py` |
| hangs on a slow dependency | one run `Deadline` caps every model and tool hop | `resilience.py` |
| flaky model provider | retry with full-jitter backoff on **retryable** errors only (429/5xx/timeouts) | `llm.py`, `agent.py` |
| flaky tool | per-tool timeout + circuit breaker; retries only for idempotent tools | `tools.py` |
| model breaks the output format | JSON-mode + tolerant parser + corrective re-prompt, capped | `agent.py` |
| model-chosen code execution | calculator via AST whitelist, never `eval`; args type-checked against the tool schema | `builtin_tools.py`, `tools.py` |

Every run ends with an explicit **outcome** (`success`, `budget_steps`,
`budget_cost`, `budget_tokens`, `deadline`, `loop_detected`, `invalid_output`,
`llm_unavailable`) instead of an unhandled exception. The outcome mix is the
SLI ([08-sre-operations/slo-catalogue.md](../08-sre-operations/slo-catalogue.md)).

**Telemetry** (`telemetry.py`): Prometheus counters and histograms for outcomes,
steps, duration, cost, tokens, tool results and model errors (all labels from
closed sets); OpenTelemetry spans `agent.run → agent.step → agent.tool`; a JSONL
run log with sizes and outcomes only, no prompt text, which feeds the drift sentinel (03).

```bash
python -m agentops "Is payments-api healthy, and can we deploy to it today?"   # needs Ollama
uvicorn agentops.server:app --port 8000      # /run, /metrics, /healthz, /readyz
pytest 01-agent-runtime                      # 20 tests, scripted model, no Ollama needed
```

`/readyz` checks the model backend, so Kubernetes takes a pod with a broken
model path out of rotation instead of letting every request time out.
