# 04 · Agent evals and experiment tracking (`agentevals`)

> JD: *"MLflow, LangFuse, LangSmith"*, *"MLOps/LLMOps"*, *"quick, low-cost
> experiments"*.

Trajectory-level evals for the incident-desk agent: not just "is the answer
right" but did it use the right tools, avoid making claims it can't back, and
end cleanly within budget.

* **Suite** ([`suites/incident-desk.yaml`](suites/incident-desk.yaml)): 12 tasks covering lookups, error-budget
  reasoning, arithmetic, runbook retrieval, multi-hop, an unknown service (robustness)
  and a destructive request it must not claim to have done (safety).
* **Checks** are named booleans (`answer_contains`, `tools_required`,
  `answer_not_contains`, `max_tool_calls`, `outcome_success`, ...), so a failure says exactly what broke.
* **k trials per task**, with **pass@1** (average) and **pass^k** (all k trials pass)
  reported. Agents are non-deterministic; pass^k is what an SLO needs.
  Flaky tasks are listed.
* **Trackers**: MLflow (params, metrics, per-tag pass rates, full result artifact),
  Langfuse (a trace per trial with scores), JSON (always, for CI).
* **Promotion gate** ([`gate.py`](agentevals/gate.py)): no drop in pass^k, ≤ 5pt drop in pass@1, ≤ 30% cost increase, ≤ +1 avg step, pass^k floor 0.7.

| Variant | Experiment |
|---|---|
| `baseline` | qwen2.5:1.5b, 6 steps |
| `candidate-0.5b` | 3x smaller model: is quality worth the savings? |
| `candidate-tight-steps` | 3 steps: latency win vs multi-hop failures |

```bash
make up && make evals          # real models, logged to MLflow at localhost:5000
make eval-compare              # gate: exit 1 if the candidate may not replace the baseline
pytest 04-agent-evals          # harness tests: a scripted "oracle" agent passes 100%, a lazy one fails
```

CI runs the real-model comparison nightly, and on any push whose commit message contains `[run-evals]`.
