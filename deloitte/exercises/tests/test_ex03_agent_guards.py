import pytest

LIMITS = {"max_steps": 6, "max_cost_usd": 0.01, "max_tokens": 12000, "deadline_s": 60}


@pytest.fixture
def m(impl):
    return impl("ex03_agent_guards")


def test_action_key_ignores_arg_order(m):
    assert m.action_key("t", {"a": 1, "b": 2}) == m.action_key("t", {"b": 2, "a": 1})
    assert m.action_key("t", {"a": 1}) != m.action_key("u", {"a": 1})
    assert m.action_key("t", {"a": 1}) != m.action_key("t", {"a": 2})


def test_loop_detector(m):
    d = m.LoopDetector(threshold=2)
    assert d.observe("search", {"q": "x"}) is False
    assert d.observe("search", {"q": "y"}) is False  # different args: not a repeat
    assert d.observe("search", {"q": "x"}) is False  # 2nd time: still allowed
    assert d.observe("search", {"q": "x"}) is True   # 3rd time: loop


@pytest.mark.parametrize("steps,cost,tokens,elapsed,expected", [
    (2, 0.001, 500, 3, None),
    (6, 0.001, 500, 3, "budget_steps"),
    (2, 0.02, 500, 3, "budget_cost"),
    (2, 0.001, 20000, 3, "budget_tokens"),
    (2, 0.001, 500, 61, "deadline"),
    (6, 0.02, 20000, 61, "budget_steps"),  # order matters: steps checked first
])
def test_budget_stop(m, steps, cost, tokens, elapsed, expected):
    assert m.budget_stop(steps, cost, tokens, elapsed, LIMITS) == expected
