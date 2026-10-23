"""Compare a current window of agent runs against a baseline window.

    python -m sentinel.monitor --runs runs.jsonl --baseline-hours 72 --current-hours 6
    python -m sentinel.monitor --baseline base.jsonl --current today.jsonl --format json
    python -m sentinel.monitor --demo cost_spike           # synthetic scenario

Exit code 1 if any finding is critical, so it can run as a CronJob/CI step
that pages, or as a pre-promotion check after a model or prompt change.
`--prom-textfile` writes gauges for the node-exporter textfile collector.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .detectors import SEVERITY_ORDER, Finding, run_all
from .synth import SCENARIOS, generate


def load(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def split_by_time(rows: list[dict], baseline_hours: float, current_hours: float, now: datetime | None = None):
    now = now or max(datetime.fromisoformat(r["ts"]) for r in rows)
    cur_start = now - timedelta(hours=current_hours)
    base_start = cur_start - timedelta(hours=baseline_hours)
    base, cur = [], []
    for r in rows:
        t = datetime.fromisoformat(r["ts"])
        if cur_start < t <= now:
            cur.append(r)
        elif base_start < t <= cur_start:
            base.append(r)
    return base, cur


def render_markdown(findings: list[Finding], n_base: int, n_cur: int) -> str:
    icon = {"ok": "ok", "info": "info", "warning": "WARN", "critical": "CRIT"}
    lines = [f"### Drift & cost sentinel ({n_base} baseline runs vs {n_cur} current runs)", "",
             "| | detector | signal | finding |", "|---|---|---|---|"]
    for f in sorted(findings, key=lambda f: -SEVERITY_ORDER[f.severity]):
        lines.append(f"| {icon[f.severity]} | {f.detector} | {f.signal} | {f.message} |")
    return "\n".join(lines)


def prom_textfile(findings: list[Finding]) -> str:
    out = ["# HELP sentinel_signal_value Drift/anomaly statistic per signal", "# TYPE sentinel_signal_value gauge",
           "# HELP sentinel_signal_severity 0 ok, 1 info, 2 warning, 3 critical", "# TYPE sentinel_signal_severity gauge"]
    for f in findings:
        lbl = f'detector="{f.detector}",signal="{f.signal}"'
        out.append(f"sentinel_signal_value{{{lbl}}} {f.value}")
        out.append(f"sentinel_signal_severity{{{lbl}}} {SEVERITY_ORDER[f.severity]}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sentinel")
    ap.add_argument("--runs", help="single run log, split by time")
    ap.add_argument("--baseline")
    ap.add_argument("--current")
    ap.add_argument("--baseline-hours", type=float, default=72)
    ap.add_argument("--current-hours", type=float, default=6)
    ap.add_argument("--demo", choices=sorted(SCENARIOS))
    ap.add_argument("--min-runs", type=int, default=50, help="refuse to judge on fewer runs than this")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--prom-textfile")
    args = ap.parse_args(argv)

    if args.demo:
        now = datetime(2026, 10, 23, 12, tzinfo=UTC)
        base = generate("normal", n=1800, hours=72, end=now - timedelta(hours=6), seed=1)
        cur = generate(args.demo, n=150, hours=6, end=now, seed=2)
    elif args.runs:
        base, cur = split_by_time(load(args.runs), args.baseline_hours, args.current_hours)
    elif args.baseline and args.current:
        base, cur = load(args.baseline), load(args.current)
    else:
        ap.error("give --runs, or --baseline and --current, or --demo")

    if len(base) < args.min_runs or len(cur) < max(10, args.min_runs // 5):
        print(f"not enough data: {len(base)} baseline / {len(cur)} current runs", file=sys.stderr)
        return 0

    findings = run_all(base, cur)
    if args.format == "json":
        print(json.dumps([f.__dict__ for f in findings], indent=2, default=str))
    else:
        print(render_markdown(findings, len(base), len(cur)))
    if args.prom_textfile:
        Path(args.prom_textfile).write_text(prom_textfile(findings))
    return 1 if any(f.severity == "critical" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
