# Exercises: LLM platform engineering (Track A)

Implement the core idea of a module yourself. Tests tell you when it's right.

| # | Exercise | Module | Concept |
|---|---|---|---|
| 01 | [PII validators](starter/ex01_pii_validators.py) | [02-guardrails](../02-guardrails/LEARN.md) | Luhn, IBAN mod-97: checksums cut false positives |
| 02 | [fix the cache leak](starter/ex02_cache_isolation.py) | [03-semantic-cache](../03-semantic-cache/LEARN.md) | tenant/prompt scoping, what's cacheable |
| 03 | [burn-rate maths](starter/ex03_burn_rate.py) | [05-llm-observability](../05-llm-observability/LEARN.md) | error budget, burn rate, multiwindow paging |
| 04 | [cost projection](starter/ex04_cost_projection.py) | [04-cost-control](../04-cost-control/LEARN.md) | shadow price, run-rate projection, budget alerts |
| 05 | [bootstrap gate](starter/ex05_bootstrap_gate.py) | [06-evals-harness](../06-evals-harness/LEARN.md) | regression vs noise |
| 06 | [cardinality guard](starter/ex06_cardinality.py) | [05-llm-observability](../05-llm-observability/LEARN.md) | bounded metric labels |

```bash
cd demandbase
make check EX=02            # one exercise against your code
make exercises              # all of them
make solutions              # reference solutions (look after you've tried!)
```

Exercise 02 is different: the starter *works* but has two production bugs. The tests describe the required behaviour.
