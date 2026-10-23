"""Wrap 05-llm-observability/prometheus/rules/slo-alerts.yml in a PrometheusRule CR
so local docker-compose and the cluster alert on exactly the same rules.

    python 08-platform-infra/scripts/gen_prometheus_rule.py          # write
    python 08-platform-infra/scripts/gen_prometheus_rule.py --check  # CI drift check
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05-llm-observability/prometheus/rules/slo-alerts.yml"
DST = ROOT / "08-platform-infra/gitops/apps/base/ai-runtime/prometheus-rule.yaml"

HEADER = "# GENERATED from 05-llm-observability/prometheus/rules/slo-alerts.yml - do not edit.\n"


def render() -> str:
    rules = yaml.safe_load(SRC.read_text())
    cr = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {"name": "ai-runtime-slos", "labels": {"app": "llm-gateway"}},
        "spec": {"groups": rules["groups"]},
    }
    return HEADER + yaml.safe_dump(cr, sort_keys=False, width=200)


if __name__ == "__main__":
    out = render()
    if "--check" in sys.argv:
        if not DST.exists() or DST.read_text() != out:
            print(f"{DST} is stale; run: python {Path(__file__).relative_to(ROOT)}")
            sys.exit(1)
        print("prometheus-rule.yaml up to date")
    else:
        DST.write_text(out)
        print(f"wrote {DST}")
