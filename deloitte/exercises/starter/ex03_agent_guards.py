"""Exercise 03: the guards that keep an agent from running away.

Implement three small functions the agent loop calls on every step.

1. `action_key(tool, args)`: a stable key for "the same action". Arg order must
   not matter: {"a": 1, "b": 2} and {"b": 2, "a": 1} are the same call.

2. `LoopDetector(threshold)`: `.observe(tool, args)` returns True once the same
   action has been seen MORE than `threshold` times (that call is the loop).

3. `budget_stop(steps, cost_usd, tokens, elapsed_s, limits)`: return the outcome
   name of the first exhausted budget, checked in this order:
       "budget_steps" (steps >= max_steps), "budget_cost" (cost >= max_cost_usd),
       "budget_tokens" (tokens >= max_tokens), "deadline" (elapsed >= deadline_s),
   or None if the run may take another step.

Run:  make check EX=03
"""


def action_key(tool: str, args: dict) -> str:
    raise NotImplementedError


class LoopDetector:
    def __init__(self, threshold: int):
        self.threshold = threshold

    def observe(self, tool: str, args: dict) -> bool:
        raise NotImplementedError


def budget_stop(steps: int, cost_usd: float, tokens: int, elapsed_s: float, limits: dict) -> str | None:
    raise NotImplementedError
