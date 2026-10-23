from agentops import demo


def test_every_demo_scenario_runs_and_ends_as_documented(capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    for outcome in ("outcome=success", "outcome=loop_detected", "outcome=invalid_output", "outcome=llm_unavailable"):
        assert outcome in out
    assert "refused_change_request" in out and "blocked_false_change_claim" in out
