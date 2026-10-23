import json
from datetime import UTC, datetime, timedelta

import pytest

from sentinel import stats
from sentinel.detectors import run_all
from sentinel.monitor import main, prom_textfile, split_by_time
from sentinel.synth import generate

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def windows(scenario):
    base = generate("normal", n=1800, hours=72, end=NOW - timedelta(hours=6), seed=1)
    cur = generate(scenario, n=150, hours=6, end=NOW, seed=2)
    return {f.signal: f for f in run_all(base, cur)}


def test_normal_traffic_raises_nothing():
    f = windows("normal")
    assert not [s for s, x in f.items() if x.severity in ("warning", "critical")], {s: x.message for s, x in f.items()}


def test_prompt_drift_flags_input_size():
    f = windows("prompt_drift")
    assert f["question_chars"].severity == "critical"
    assert f["cost_per_run"].severity in ("ok", "warning")  # longer questions cost a bit more, not 2x


def test_model_regression_flags_quality_and_model_change():
    f = windows("model_regression")
    assert f["invalid_output_rate"].severity == "critical"
    assert f["budget_stop_rate"].severity == "critical"
    assert f["outcome"].severity == "critical"
    assert f["model"].severity == "critical"


def test_cost_spike_flags_cost_not_input():
    f = windows("cost_spike")
    assert f["cost_per_run"].severity == "critical"
    assert f["hourly_spend"].severity == "critical"
    assert f["prompt_tokens"].severity == "critical"
    assert f["question_chars"].severity == "ok"  # users didn't change; the system did


def test_tool_outage_flags_tool_errors_and_tool_mix():
    f = windows("tool_outage")
    assert f["tool_error_rate"].severity == "critical"
    assert f["tools"].severity in ("warning", "critical")


def test_stats_basics():
    assert stats.psi([1, 2, 3, 4] * 50, [1, 2, 3, 4] * 50) == pytest.approx(0, abs=1e-9)
    assert stats.psi(list(range(100)), [x + 100 for x in range(100)]) > 0.25
    assert stats.js_divergence({"a": 1.0}, {"a": 1.0}) == 0
    assert stats.js_divergence({"a": 1.0}, {"b": 1.0}) == pytest.approx(1.0)
    assert stats.robust_z(100, [10, 11, 9, 10, 12, 10, 8]) > 20
    assert stats.two_proportion_z(10, 1000, 50, 1000) > 5


def test_split_by_time_and_cli(tmp_path, capsys):
    rows = generate("normal", n=600, hours=72, end=NOW - timedelta(hours=6), seed=1) + \
        generate("cost_spike", n=100, hours=6, end=NOW, seed=2)
    base, cur = split_by_time(rows, baseline_hours=72, current_hours=6)
    assert len(base) == 600 and len(cur) == 100

    log = tmp_path / "runs.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in rows))
    tf = tmp_path / "sentinel.prom"
    assert main(["--runs", str(log), "--prom-textfile", str(tf)]) == 1  # critical -> exit 1
    out = capsys.readouterr().out
    assert "CRIT" in out and "cost_per_run" in out
    assert 'sentinel_signal_severity{detector="cost_anomaly",signal="cost_per_run"} 3' in tf.read_text()


def test_refuses_to_judge_tiny_samples(tmp_path):
    log = tmp_path / "runs.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in generate("cost_spike", n=20, hours=6, end=NOW)))
    assert main(["--runs", str(log)]) == 0


def test_textfile_format():
    f = windows("normal")
    text = prom_textfile(list(f.values()))
    assert text.count("sentinel_signal_value{") == len(f)


def test_traffic_growth_alone_is_not_a_cost_anomaly():
    # 20% more runs per hour with unchanged per-run behaviour: growth, not an anomaly.
    base = generate("normal", n=1500, hours=72, end=NOW - timedelta(hours=6), seed=1)
    cur = generate("normal", n=150, hours=6, end=NOW, seed=2)
    f = {x.signal: x for x in run_all(base, cur)}
    assert f["hourly_spend"].severity == "ok", f["hourly_spend"].message
