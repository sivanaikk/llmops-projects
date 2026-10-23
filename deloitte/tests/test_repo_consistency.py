"""Repo-level checks: alerts point at real runbooks, and docs match the code."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "observability" / "prometheus" / "rules"


def all_alerts():
    for f in RULES.glob("*.yml"):
        if f.name.endswith(".test.yml"):
            continue
        for g in yaml.safe_load(f.read_text())["groups"]:
            for r in g["rules"]:
                if "alert" in r:
                    yield f.name, r


def test_every_alert_has_an_existing_runbook():
    missing = []
    for fname, r in all_alerts():
        url = r.get("annotations", {}).get("runbook_url")
        if not url or not (ROOT / url).is_file():
            missing.append((fname, r["alert"], url))
    assert not missing, missing


def test_every_alert_has_severity_and_owner_routing():
    for _, r in all_alerts():
        labels = r.get("labels", {})
        assert labels.get("severity") in ("page", "ticket"), r["alert"]


def test_slo_outcomes_match_agent_outcomes():
    from agentops.agent import OUTCOMES

    spec = yaml.safe_load((ROOT / "02-error-budget-gate/slos/agent-runtime.yaml").read_text())
    slo_errors = set(re.search(r'outcome=~"([^"]+)"', spec["sli"]["errors"]).group(1).split("|"))
    assert slo_errors <= set(OUTCOMES), slo_errors - set(OUTCOMES)
    # budget/loop stops are deliberately NOT SLO errors (see 08-sre-operations/slo-catalogue.md)
    assert not slo_errors & {"budget_steps", "budget_cost", "budget_tokens", "loop_detected"}
