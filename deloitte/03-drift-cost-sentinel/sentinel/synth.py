"""Synthetic agent run logs (same schema as agentops' JSONL run log), for
tests, demos and for checking the detectors fire on the failures they target."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

TOOLS = ["get_service_status", "get_error_budget", "search_runbooks", "read_runbook", "calculator"]

SCENARIOS = {
    "normal": "baseline behaviour",
    "prompt_drift": "users paste long incident logs into questions (input drift)",
    "model_regression": "a model/prompt change breaks the JSON protocol and causes loops",
    "cost_spike": "a retrieval change stuffs much more context into every prompt",
    "tool_outage": "a tool dependency fails; the agent errors and loops around it",
}


def generate(scenario: str, n: int, hours: float, end: datetime, seed: int = 0, model: str = "qwen2.5:1.5b") -> list[dict]:
    rng = random.Random(seed)
    start = end - timedelta(hours=hours)
    rows = []
    for i in range(n):
        q_chars = max(10, int(rng.lognormvariate(4.2, 0.4)))
        steps = rng.choices([2, 3, 4, 5], weights=[30, 45, 20, 5])[0]
        outcome = rng.choices(["success", "budget_steps", "llm_unavailable", "invalid_output"], weights=[95, 2, 2, 1])[0]
        invalid = 1 if rng.random() < 0.03 else 0
        tool_errors = 1 if rng.random() < 0.04 else 0
        tools = rng.sample(TOOLS[:3], k=min(steps - 1, 3))
        m = model

        if scenario == "prompt_drift":
            q_chars = int(q_chars * rng.uniform(4, 9))
        elif scenario == "model_regression":
            m = "qwen2.5:0.5b"
            invalid = 1 if rng.random() < 0.35 else 0
            outcome = rng.choices(["success", "invalid_output", "loop_detected", "budget_steps"], weights=[60, 15, 15, 10])[0]
            steps = min(6, steps + rng.choice([1, 2, 3]))
        elif scenario == "tool_outage":
            tool_errors = 1 if rng.random() < 0.6 else 0
            tools = ["get_service_status"] * 2 + tools
            outcome = rng.choices(["success", "loop_detected", "budget_steps"], weights=[55, 30, 15])[0]

        prompt_tokens = int(steps * (450 + q_chars / 4) * rng.uniform(0.9, 1.1))
        if scenario == "cost_spike":
            prompt_tokens *= 4
        completion_tokens = int(steps * rng.uniform(40, 90))
        cost = (prompt_tokens * 0.2 + completion_tokens * 0.8) / 1e6
        ts = start + timedelta(seconds=(i + rng.random()) * hours * 3600 / n)
        rows.append({
            "ts": ts.isoformat(), "agent": "incident-desk", "run_id": f"{scenario}-{seed}-{i}", "model": m,
            "outcome": outcome, "steps": steps, "tools": tools, "tool_errors": tool_errors,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost_usd": round(cost, 8),
            "duration_s": round(steps * rng.uniform(0.8, 2.5), 3), "question_chars": q_chars,
            "answer_chars": int(rng.uniform(80, 400)), "invalid_outputs": invalid,
        })
    return rows
