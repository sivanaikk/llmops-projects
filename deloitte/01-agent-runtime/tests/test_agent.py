import json
import time

import pytest

from agentops import Agent, AgentConfig, LLMError, ScriptedLLM, Telemetry, Tool, ToolError, ToolRegistry, default_tools
from agentops.agent import parse_action
from agentops.builtin_tools import calculator, search_runbooks
from agentops.resilience import CircuitBreaker, CircuitOpen, Deadline, DeadlineExceeded, retry_call


def act(action, **kw):
    return json.dumps({"thought": "t", "action": action, **kw})


def make(script, tools=None, **cfg):
    tm = Telemetry()
    agent = Agent(ScriptedLLM(script), ToolRegistry(tools or default_tools()), AgentConfig(**cfg), tm, sleep=lambda s: None)
    return agent, tm


def runs(tm, outcome):
    return tm.registry.get_sample_value("agent_runs_total", {"agent": "incident-desk", "outcome": outcome}) or 0


def test_happy_path_uses_tools_then_answers():
    agent, tm = make([
        act("get_service_status", args={"service": "payments-api"}),
        act("get_error_budget", args={"service": "payments-api"}),
        act("final", answer="payments-api is degraded (INC-1042); budget 18% left, gate open."),
    ])
    r = agent.run("Is payments-api healthy and can we deploy?")
    assert r.outcome == "success"
    assert [c.tool for c in r.tool_calls] == ["get_service_status", "get_error_budget"]
    assert all(c.ok for c in r.tool_calls)
    assert r.steps == 3 and r.cost_usd > 0
    assert runs(tm, "success") == 1


def test_observations_reach_the_model():
    llm = ScriptedLLM([act("get_service_status", args={"service": "doc-ingest"}), act("final", answer="down")])
    Agent(llm, ToolRegistry(default_tools()), sleep=lambda s: None).run("doc-ingest?")
    assert "INC-1045" in llm.calls[1][-1]["content"]


def test_tool_error_is_fed_back_and_recoverable():
    agent, tm = make([
        act("get_service_status", args={"service": "payments"}),
        act("get_service_status", args={"service": "payments-api"}),
        act("final", answer="ok"),
    ])
    r = agent.run("payments?")
    assert r.outcome == "success"
    assert r.tool_calls[0].error_kind == "not_found" and r.tool_calls[1].ok


def test_step_budget():
    agent, tm = make([act("calculator", args={"expression": f"{i}+1"}) for i in range(20)], max_steps=3)
    r = agent.run("loop")
    assert r.outcome == "budget_steps" and r.steps == 3
    assert "Partial findings" in r.answer


def test_loop_detection():
    agent, _ = make([act("search_runbooks", args={"query": "latency"})] * 10, loop_threshold=2)
    r = agent.run("latency?")
    assert r.outcome == "loop_detected"
    assert len(r.tool_calls) == 2


def test_cost_budget():
    agent, _ = make([act("calculator", args={"expression": "1+1"}) + " " * 4000] * 10, max_cost_usd=0.002)
    assert agent.run("x").outcome == "budget_cost"


def test_invalid_output_is_corrected_then_capped():
    agent, tm = make(["sure! here you go", act("final", answer="fixed")])
    r = agent.run("q")
    assert r.outcome == "success" and r.invalid_outputs == 1

    agent, tm = make(["nope"] * 5, max_invalid_outputs=2)
    r = agent.run("q")
    assert r.outcome == "invalid_output"
    assert tm.registry.get_sample_value("agent_invalid_outputs_total", {"agent": "incident-desk"}) == 3


def test_retryable_llm_errors_are_retried_then_fail_cleanly():
    agent, tm = make([LLMError("503", retryable=True), act("final", answer="recovered")])
    assert agent.run("q").outcome == "success"

    agent, tm = make([LLMError("503", retryable=True)] * 5)
    r = agent.run("q")
    assert r.outcome == "llm_unavailable" and "unavailable" in r.answer
    assert tm.registry.get_sample_value("agent_llm_errors_total", {"agent": "incident-desk", "retryable": "true"}) == 3


def test_non_retryable_llm_error_is_not_retried():
    llm = ScriptedLLM([LLMError("400 bad request", retryable=False), act("final", answer="x")])
    r = Agent(llm, ToolRegistry(default_tools()), sleep=lambda s: None).run("q")
    assert r.outcome == "llm_unavailable" and len(llm.calls) == 1


def test_deadline_caps_slow_tool():
    slow = Tool("slow", "sleeps", {"s": "number"}, lambda s: time.sleep(s) or "done", timeout_s=5, idempotent=False)
    agent, _ = make([act("slow", args={"s": 2})] + [act("final", answer="x")], tools=[slow], deadline_s=0.3)
    t0 = time.perf_counter()
    r = agent.run("q")
    assert time.perf_counter() - t0 < 1.5
    assert r.outcome == "deadline" or r.tool_calls[0].error_kind == "timeout"


def test_run_log_written(tmp_path):
    log = tmp_path / "runs.jsonl"
    tm = Telemetry(run_log=log)
    Agent(ScriptedLLM([act("final", answer="hi")]), ToolRegistry(default_tools()), telemetry=tm).run("hello there")
    rec = json.loads(log.read_text().splitlines()[0])
    assert rec["outcome"] == "success" and rec["question_chars"] == 11
    assert "hello" not in log.read_text()  # sizes only, never prompt text


def test_parse_action_tolerates_fences_and_chatter():
    assert parse_action('```json\n{"action": "final", "answer": "a"}\n```')["answer"] == "a"
    assert parse_action('Sure: {"action": "calculator", "args": {"expression": "1"}} hope that helps')["action"] == "calculator"
    with pytest.raises(ValueError):
        parse_action('{"action": "final"}')


def test_tool_validation():
    reg = ToolRegistry(default_tools())
    for args, kind in [({"service": 3}, "bad_args"), ({}, "bad_args"), ({"service": "x", "y": 1}, "bad_args")]:
        with pytest.raises(ToolError) as e:
            reg.call("get_service_status", args)
        assert e.value.kind == kind
    with pytest.raises(ToolError) as e:
        reg.call("rm_rf", {})
    assert e.value.kind == "unknown_tool"


def test_calculator_is_safe():
    assert calculator("(1 - 0.18) * 100") == 82.0
    for bad in ["__import__('os').system('id')", "2**999999", "open('x')"]:
        with pytest.raises(ToolError):
            calculator(bad)


def test_runbook_search_ranks_by_tags():
    assert search_runbooks("p95 latency is high")[0]["runbook"] == "high-latency"
    assert search_runbooks("azure openai 429")[0]["runbook"] == "llm-provider-degraded"


def test_circuit_breaker_opens_and_half_opens():
    t = [0.0]
    cb = CircuitBreaker("dep", failure_threshold=2, reset_timeout=10, clock=lambda: t[0])

    def boom():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(boom)
    assert cb.state == "open"
    with pytest.raises(CircuitOpen):
        cb.call(lambda: 1)
    t[0] = 11
    assert cb.state == "half_open"
    assert cb.call(lambda: 1) == 1 and cb.state == "closed"


def test_breaker_short_circuits_failing_tool():
    calls = []

    def flaky(x):
        calls.append(x)
        raise RuntimeError("dependency down")

    reg = ToolRegistry([Tool("flaky", "fails", {"x": "string"}, flaky, idempotent=False)], breaker_threshold=2)
    kinds = []
    for _ in range(4):
        with pytest.raises(ToolError) as e:
            reg.call("flaky", {"x": "a"})
        kinds.append(e.value.kind)
    assert kinds == ["error", "error", "circuit_open", "circuit_open"]
    assert len(calls) == 2  # the dependency stops getting hammered


def test_retry_respects_deadline():
    t = [0.0]
    d = Deadline(1.0, clock=lambda: t[0])

    def fail():
        t[0] += 0.6
        raise RuntimeError("x")

    with pytest.raises(DeadlineExceeded):
        retry_call(fail, attempts=10, deadline=d, sleep=lambda s: None)
    assert t[0] <= 1.8
