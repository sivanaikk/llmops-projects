from pathlib import Path

from evalkit import DEFAULT_SCORERS, Example, Output, compare, load_dataset, run
from evalkit.compare import paired_bootstrap, render_markdown
from evalkit.runner import RunResult
from evalkit.scorers import Abstention, FactRecall, LLMJudgeFaithfulness, parse_judge_score

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "account_qa.jsonl"


def ex(**kw):
    base = dict(id="x", question="q", must_include=["Priya Raman"], source="northwind-robotics#buying-group")
    base.update(kw)
    return Example(**base)


def test_dataset_loads_and_has_unanswerables():
    ds = load_dataset(DATASET)
    assert len(ds) >= 15
    assert any(not e.answerable for e in ds)


def test_fact_recall_and_abstention():
    assert FactRecall()(ex(), Output("The economic buyer is priya  raman.", [], [])) == 1.0
    unans = ex(must_include=["don't know"], source=None)
    assert FactRecall()(unans, Output("I don’t know based on the account notes.", [], [])) == 1.0
    assert Abstention()(unans, Output("The CFO is Bob.", [], [])) == 0.0
    assert Abstention()(ex(), Output("I don't know based on the account notes.", [], [])) == 0.0


def test_judge_parsing_is_robust():
    assert parse_judge_score('Sure! {"score": 4, "reason": "ok"}') == 4
    assert parse_judge_score('score: 2') == 2
    assert parse_judge_score("I think it's good") is None
    j = LLMJudgeFaithfulness(lambda m: '{"score": 5, "reason": "supported"}')
    assert j(ex(), Output("Priya Raman", ["ctx"], [])) == 1.0


def oracle(question):
    # Pretend system: answers correctly by looking the fact up in the dataset.
    e = next(e for e in load_dataset(DATASET) if e.question == question)
    ans = "I don't know based on the account notes." if not e.answerable else " ".join(e.must_include)
    return Output(ans, [], [e.source] if e.source else [], latency_s=0.5)


def broken(question):
    if "intent score" in question or "economic buyer" in question:
        raise RuntimeError("upstream 503")
    return Output("Something unrelated.", [], [], latency_s=0.6)


def test_compare_flags_regression(tmp_path):
    ds = load_dataset(DATASET)
    base = run("base", oracle, ds, DEFAULT_SCORERS)
    cand = run("cand", broken, ds, DEFAULT_SCORERS)
    assert base.summary["scores"]["fact_recall"] == 1.0
    assert cand.summary["errors"] == 3  # q01, q02, q15

    base.save(tmp_path)
    cand.save(tmp_path)
    deltas, failures = compare(RunResult.load(tmp_path, "base"), RunResult.load(tmp_path, "cand"))
    assert any(d.metric == "fact_recall" and d.regression for d in deltas)
    assert any("error rate" in f for f in failures)
    assert "Gate: FAIL" in render_markdown(base, cand, deltas, failures)


def test_identical_runs_pass_gate():
    ds = load_dataset(DATASET)
    a, b = run("a", oracle, ds, DEFAULT_SCORERS), run("b", oracle, ds, DEFAULT_SCORERS)
    deltas, failures = compare(a, b)
    assert failures == [] and not any(d.regression for d in deltas)


def test_bootstrap_ci_contains_mean():
    lo, hi = paired_bootstrap([0.0, 0.1, -0.1, 0.05, 0.0] * 10)
    assert lo <= 0.01 <= hi
