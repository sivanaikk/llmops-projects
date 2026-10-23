"""agentevals CLI.

    python -m agentevals run variants/baseline.yaml --trials 3 --tracker mlflow
    python -m agentevals run variants/candidate-0.5b.yaml --trials 3
    python -m agentevals compare baseline candidate-0.5b      # exit 1 if the gate fails
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .gate import evaluate, render
from .runner import run_suite
from .suite import load_suite
from .trackers import JsonTracker, LangfuseTracker, MLflowTracker

HERE = Path(__file__).resolve().parents[1]


def build_agent(variant: dict):
    from agentops import Agent, AgentConfig, OpenAICompatClient, ToolRegistry, default_tools

    def fn(question: str):
        # Fresh registry per trial: one trial's open circuit must not fail the next.
        agent = Agent(OpenAICompatClient(model=variant["model"]), ToolRegistry(default_tools()),
                      AgentConfig(max_steps=variant.get("max_steps", 6)))
        r = agent.run(question)
        # Attempted calls count: looking up an unknown service and reporting the error is correct behaviour.
        return r.outcome, r.answer, [c.tool for c in r.tool_calls], r.steps, r.cost_usd

    return fn


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agentevals")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("variant", type=Path)
    r.add_argument("--suite", type=Path, default=HERE / "suites" / "incident-desk.yaml")
    r.add_argument("--trials", type=int, default=3)
    r.add_argument("--concurrency", type=int, default=2)
    r.add_argument("--tracker", choices=["json", "mlflow", "langfuse"], action="append", default=None)
    r.add_argument("--out", type=Path, default=HERE / "results")
    c = sub.add_parser("compare")
    c.add_argument("baseline")
    c.add_argument("candidate")
    c.add_argument("--out", type=Path, default=HERE / "results")
    c.add_argument("--report", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "run":
        variant = yaml.safe_load(args.variant.read_text())
        tasks = load_suite(args.suite)
        result = run_suite(variant["name"], build_agent(variant), tasks, k=args.trials, concurrency=args.concurrency)
        params = {**variant, "suite": args.suite.stem, "trials": args.trials}
        trackers = [JsonTracker(args.out)]
        for name in sorted(set(args.tracker or []) - {"json"}):
            trackers.append(MLflowTracker() if name == "mlflow" else LangfuseTracker())
        for t in trackers:
            print(f"logged to {type(t).__name__}: {t.log(result, params)}", file=sys.stderr)
        print(json.dumps(result.summary, indent=2))
        return 0

    base = json.loads((args.out / f"{args.baseline}.json").read_text())["summary"]
    cand = json.loads((args.out / f"{args.candidate}.json").read_text())["summary"]
    failures = evaluate(base, cand)
    md = render(base, cand, failures)
    print(md)
    if args.report:
        args.report.write_text(md)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
