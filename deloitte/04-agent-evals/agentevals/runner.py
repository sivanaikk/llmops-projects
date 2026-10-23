"""Run a suite against an agent, K trials per task.

Agents are non-deterministic even at temperature 0 (batching, retries,
provider changes), so one pass per task overstates reliability. We report:

* pass@1  - mean per-trial pass rate (what a single user sees on average)
* pass^k  - share of tasks that passed in *all* k trials (what an SLO needs)
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .suite import Task, check

# A system under test: question -> (outcome, answer, tools called, steps, cost_usd)
AgentFn = Callable[[str], tuple[str, str, list[str], int, float]]


@dataclass
class Trial:
    task_id: str
    trial: int
    passed: bool
    checks: dict[str, bool]
    outcome: str
    steps: int
    tools: list[str]
    cost_usd: float
    latency_s: float
    answer: str
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    variant: str
    trials: list[Trial]
    summary: dict

    def to_dict(self) -> dict:
        return {"variant": self.variant, "summary": self.summary, "trials": [asdict(t) for t in self.trials]}


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def summarize(variant: str, tasks: list[Task], trials: list[Trial], k: int) -> dict:
    by_task: dict[str, list[Trial]] = {}
    for t in trials:
        by_task.setdefault(t.task_id, []).append(t)
    failing_checks: dict[str, int] = {}
    for t in trials:
        for name, ok in t.checks.items():
            if not ok:
                failing_checks[name] = failing_checks.get(name, 0) + 1
    by_tag: dict[str, list[float]] = {}
    for task in tasks:
        rate = statistics.fmean(t.passed for t in by_task.get(task.id, [])) if by_task.get(task.id) else 0.0
        for tag in task.tags:
            by_tag.setdefault(tag, []).append(rate)
    return {
        "variant": variant,
        "tasks": len(tasks),
        "trials_per_task": k,
        "pass_at_1": round(statistics.fmean(t.passed for t in trials), 4) if trials else 0.0,
        "pass_hat_k": round(statistics.fmean(all(t.passed for t in ts) for ts in by_task.values()), 4) if by_task else 0.0,
        "success_outcome_rate": round(statistics.fmean(t.outcome == "success" for t in trials), 4) if trials else 0.0,
        "avg_steps": round(statistics.fmean(t.steps for t in trials), 3) if trials else 0.0,
        "avg_cost_usd": round(statistics.fmean(t.cost_usd for t in trials), 8) if trials else 0.0,
        "latency_p95_s": round(_pct([t.latency_s for t in trials], 0.95), 3),
        "pass_rate_by_tag": {k_: round(statistics.fmean(v), 4) for k_, v in sorted(by_tag.items())},
        "failing_checks": dict(sorted(failing_checks.items(), key=lambda kv: -kv[1])),
        "flaky_tasks": sorted(tid for tid, ts in by_task.items() if 0 < sum(t.passed for t in ts) < len(ts)),
    }


def run_suite(variant: str, agent: AgentFn, tasks: list[Task], k: int = 3, concurrency: int = 2) -> EvalResult:
    def one(args: tuple[Task, int]) -> Trial:
        task, i = args
        t0 = time.perf_counter()
        try:
            outcome, answer, tools, steps, cost = agent(task.question)
        except Exception as e:  # a crash is a failed trial, not a crashed eval
            outcome, answer, tools, steps, cost = "harness_error", f"{type(e).__name__}: {e}", [], 0, 0.0
        checks = check(task, outcome, answer, tools, steps)
        return Trial(task.id, i, all(checks.values()), checks, outcome, steps, tools, cost,
                     time.perf_counter() - t0, answer[:500], task.tags)

    jobs = [(task, i) for task in tasks for i in range(k)]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        trials = list(pool.map(one, jobs))
    return EvalResult(variant, trials, summarize(variant, tasks, trials, k))
