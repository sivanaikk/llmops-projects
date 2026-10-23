"""Task suites and per-trial checks for agent evals.

Agent evals check the *trajectory*, not just the final text: did it call the
tools it needed, avoid the ones it shouldn't, stay within budget, and end
with outcome=success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Task:
    id: str
    question: str
    expect: dict
    tags: list[str] = field(default_factory=list)


def load_suite(path: str | Path) -> list[Task]:
    raw = yaml.safe_load(Path(path).read_text())
    return [Task(t["id"], t["question"], t.get("expect", {}), t.get("tags", [])) for t in raw["tasks"]]


def _has(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def check(task: Task, outcome: str, answer: str, tools: list[str], steps: int) -> dict[str, bool]:
    """Every check is a named boolean, so failures say exactly what went wrong."""
    e = task.expect
    checks: dict[str, bool] = {"outcome_success": outcome == "success"}
    if "answer_contains" in e:
        checks["answer_contains"] = all(_has(answer, s) for s in e["answer_contains"])
    if "answer_contains_any" in e:
        checks["answer_contains_any"] = any(_has(answer, s) for s in e["answer_contains_any"])
    if "answer_not_contains" in e:
        checks["answer_not_contains"] = not any(_has(answer, s) for s in e["answer_not_contains"])
    if "tools_required" in e:
        checks["tools_required"] = set(e["tools_required"]) <= set(tools)
    if "tools_forbidden" in e:
        checks["tools_forbidden"] = not (set(e["tools_forbidden"]) & set(tools))
    if "max_tool_calls" in e:
        checks["max_tool_calls"] = len(tools) <= e["max_tool_calls"]
    if "max_steps" in e:
        checks["max_steps"] = steps <= e["max_steps"]
    return checks
