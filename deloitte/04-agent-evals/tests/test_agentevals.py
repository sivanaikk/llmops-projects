import json
import re
from pathlib import Path

from agentevals.gate import GatePolicy, evaluate, render
from agentevals.runner import run_suite
from agentevals.suite import Task, check, load_suite
from agentevals.trackers import JsonTracker, MLflowTracker
from agentops import Agent, AgentConfig, ScriptedLLM, ToolRegistry, default_tools

SUITE = Path(__file__).resolve().parents[1] / "suites" / "incident-desk.yaml"


def act(action, **kw):
    return json.dumps({"thought": "t", "action": action, **kw})


def plan(q: str) -> list[tuple[str, dict]]:
    svc = re.search(r"[a-z]+-(?:api|ingest|service|gateway)", q)
    svc = svc.group(0) if svc else ""
    ql = q.lower()
    if ql.startswith("delete"):
        return []
    if "minutes of downtime" in ql:
        return [("calculator", {"expression": "0.005*28*24*60"})]
    if "runbook" in ql and "first" in ql:
        return [("read_runbook", {"name": "service-down"})]
    if "runbook" in ql:
        return [("search_runbooks", {"query": q})]
    steps = []
    if any(w in ql for w in ("healthy", "degraded", "status", "owns", "incident")):
        steps.append(("get_service_status", {"service": svc}))
    if any(w in ql for w in ("budget", "gate", "ship")):
        steps.append(("get_error_budget", {"service": svc}))
    return steps


def oracle(messages):
    """A policy that does what a good model should: plan tools, then answer from observations."""
    q = messages[1]["content"]
    obs = [m["content"] for m in messages if m["role"] == "user" and m["content"].startswith("Observation")]
    p = plan(q)
    if len(obs) < len(p):
        name, args = p[len(obs)]
        return act(name, args=args)
    if not p:
        return act("final", answer="I can't do that: I only have read-only tools.")
    return act("final", answer=" ".join(obs))


def lazy(messages):
    """A bad policy: answers immediately without looking anything up."""
    return act("final", answer="Everything looks fine.")


def agent_fn(policy):
    def fn(question):
        r = Agent(ScriptedLLM(policy), ToolRegistry(default_tools()), AgentConfig(), sleep=lambda s: None).run(question)
        return r.outcome, r.answer, [c.tool for c in r.tool_calls], r.steps, r.cost_usd
    return fn


def test_suite_loads():
    tasks = load_suite(SUITE)
    assert len(tasks) >= 12 and {"safety", "robustness", "multi-hop"} <= {t for x in tasks for t in x.tags}


def test_oracle_passes_everything():
    res = run_suite("oracle", agent_fn(oracle), load_suite(SUITE), k=2)
    failed = [(t.task_id, t.checks) for t in res.trials if not t.passed]
    assert not failed, failed
    assert res.summary["pass_at_1"] == 1.0 and res.summary["pass_hat_k"] == 1.0


def test_lazy_agent_fails_tool_checks():
    res = run_suite("lazy", agent_fn(lazy), load_suite(SUITE), k=1)
    assert res.summary["pass_at_1"] < 0.2
    assert res.summary["failing_checks"]["tools_required"] >= 10


def test_flaky_task_counts_against_pass_hat_k():
    calls = {"n": 0}

    def flaky(question):
        calls["n"] += 1
        return ("success", "degraded", ["get_service_status"], 2, 0.0) if calls["n"] % 2 else ("deadline", "", [], 6, 0.0)

    task = Task("t", "q", {"answer_contains": ["degraded"], "tools_required": ["get_service_status"]})
    res = run_suite("flaky", flaky, [task], k=4, concurrency=1)
    assert res.summary["pass_at_1"] == 0.5 and res.summary["pass_hat_k"] == 0.0
    assert res.summary["flaky_tasks"] == ["t"]


def test_harness_survives_agent_crash():
    def boom(q):
        raise RuntimeError("segfault in tool")
    res = run_suite("boom", boom, [Task("t", "q", {})], k=1)
    assert res.trials[0].outcome == "harness_error" and not res.trials[0].passed


def test_checks():
    t = Task("x", "q", {"answer_not_contains": ["deleted"], "max_tool_calls": 0})
    assert all(check(t, "success", "I can't do that", [], 1).values())
    assert not check(t, "success", "Deleted it!", [], 1)["answer_not_contains"]


def test_gate():
    base = run_suite("base", agent_fn(oracle), load_suite(SUITE), k=1).summary
    bad = run_suite("bad", agent_fn(lazy), load_suite(SUITE), k=1).summary
    failures = evaluate(base, bad)
    assert any("pass@1" in f for f in failures) and any("floor" in f for f in failures)
    assert evaluate(base, base) == []
    assert "Gate: FAIL" in render(base, bad, failures)
    pricey = dict(base, avg_cost_usd=base["avg_cost_usd"] * 2)
    assert any("cost" in f for f in evaluate(base, pricey, GatePolicy()))


def test_trackers(tmp_path, monkeypatch):
    res = run_suite("oracle", agent_fn(oracle), load_suite(SUITE), k=1)
    path = JsonTracker(tmp_path).log(res, {"model": "scripted"})
    assert json.loads(Path(path).read_text())["summary"]["pass_at_1"] == 1.0

    import mlflow

    # Local test only: the lab's MLflow runs as a server (docker-compose), reached over HTTP.
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    run_id = MLflowTracker(tracking_uri=f"file://{tmp_path / 'mlruns'}").log(res, {"model": "scripted", "suite": "incident-desk"})
    run = mlflow.get_run(run_id)
    assert run.data.metrics["pass_at_1"] == 1.0 and run.data.params["model"] == "scripted"
    assert run.data.metrics["pass_rate.safety"] == 1.0
