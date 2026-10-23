import json


def action_key(tool: str, args: dict) -> str:
    return f"{tool}:{json.dumps(args, sort_keys=True)}"


class LoopDetector:
    def __init__(self, threshold: int):
        self.threshold = threshold
        self.seen: dict[str, int] = {}

    def observe(self, tool: str, args: dict) -> bool:
        k = action_key(tool, args)
        self.seen[k] = self.seen.get(k, 0) + 1
        return self.seen[k] > self.threshold


def budget_stop(steps, cost_usd, tokens, elapsed_s, limits):
    if steps >= limits["max_steps"]:
        return "budget_steps"
    if cost_usd >= limits["max_cost_usd"]:
        return "budget_cost"
    if tokens >= limits["max_tokens"]:
        return "budget_tokens"
    if elapsed_s >= limits["deadline_s"]:
        return "deadline"
    return None
