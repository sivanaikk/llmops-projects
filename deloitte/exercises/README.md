# Exercises: Applied AI SRE (Track B)

Implement the core idea of a module yourself. Tests tell you when it's right.

| # | Exercise | Module | Concept |
|---|---|---|---|
| 01 | [circuit breaker](starter/ex01_circuit_breaker.py) | [01-agent-runtime](../01-agent-runtime/LEARN.md) | closed → open → half-open state machine |
| 02 | [retry with jitter + deadline](starter/ex02_retry.py) | [01-agent-runtime](../01-agent-runtime/LEARN.md) | retry only what's transient; never past the deadline |
| 03 | [agent guards](starter/ex03_agent_guards.py) | [01-agent-runtime](../01-agent-runtime/LEARN.md) | loop detection, budget order |
| 04 | [PSI drift](starter/ex04_psi.py) | [03-drift-cost-sentinel](../03-drift-cost-sentinel/LEARN.md) | distribution shift |
| 05 | [pass@1, pass^k, pass@k](starter/ex05_pass_k.py) | [04-agent-evals](../04-agent-evals/LEARN.md) | measuring non-deterministic agents |
| 06 | [capacity](starter/ex06_capacity.py) | [05-resilience](../05-resilience/LEARN.md) | Little's law |
| 07 | [release decision (Go)](go/burnrate/starter.go) | [02-error-budget-gate](../02-error-budget-gate/LEARN.md) | burn rate, budget, gate policy |

```bash
cd deloitte
make check EX=01            # one exercise against your code
make exercises              # all of them
make check-go               # exercise 07
make solutions              # reference solutions (look after you've tried!)
```

Each starter file's docstring is the full spec. Edit only `starter/` (and `go/burnrate/starter.go`).
