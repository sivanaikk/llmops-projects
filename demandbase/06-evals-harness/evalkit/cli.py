"""evalkit CLI.

    python -m evalkit run variants/baseline.yaml
    python -m evalkit run variants/candidate-prompt-v2.yaml --judge
    python -m evalkit compare baseline candidate-prompt-v2     # exit 1 on regression
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .compare import compare, render_markdown
from .runner import RunResult, load_dataset, run
from .scorers import DEFAULT_SCORERS, LLMJudgeFaithfulness, Output

HERE = Path(__file__).resolve().parents[1]


def build_system(variant: dict):
    """Wire the Account Intel app (07) as the system under test."""
    from account_rag import AccountAssistant, AssistantConfig
    from account_rag.gateway import GatewayClient
    from llmobs import LLMTracer

    cfg = AssistantConfig(model=variant["model"], prompt_version=variant["prompt_version"], top_k=variant.get("top_k", 3),
                          temperature=variant.get("temperature", 0), max_tokens=variant.get("max_tokens", 200),
                          use_cache=False)  # never let a cache answer an eval
    app = AccountAssistant(GatewayClient(), cfg, tracer=LLMTracer(capture_ratio=0))

    def system(question: str) -> Output:
        a = app.answer(question)
        return Output(a.text, a.contexts, a.sources, a.latency_s,
                      int(a.usage.get("prompt_tokens") or 0), int(a.usage.get("completion_tokens") or 0))

    return system


def judge_chat():
    from account_rag.gateway import GatewayClient

    client = GatewayClient()
    return lambda messages: client.chat("judge", messages, feature="eval-judge", temperature=0, max_tokens=120)[
        "choices"][0]["message"]["content"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evalkit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("variant", type=Path)
    r.add_argument("--dataset", type=Path, default=HERE / "datasets" / "account_qa.jsonl")
    r.add_argument("--out", type=Path, default=HERE / "results")
    r.add_argument("--judge", action="store_true", help="add LLM-as-judge faithfulness (uses the `judge` model)")
    r.add_argument("--concurrency", type=int, default=2)
    c = sub.add_parser("compare")
    c.add_argument("baseline")
    c.add_argument("candidate")
    c.add_argument("--out", type=Path, default=HERE / "results")
    c.add_argument("--report", type=Path, help="write markdown report here (e.g. for an MR comment)")
    args = ap.parse_args(argv)

    if args.cmd == "run":
        variant = yaml.safe_load(args.variant.read_text())
        scorers = list(DEFAULT_SCORERS)
        judge = LLMJudgeFaithfulness(judge_chat()) if args.judge else None
        if judge:
            scorers.append(judge)
        res = run(variant["name"], build_system(variant), load_dataset(args.dataset), scorers, args.concurrency)
        if judge:
            # An unparseable verdict scores 0; a high count means the judge is broken, not the candidate.
            res.summary["judge_parse_failures"] = judge.parse_failures
            if judge.parse_failures:
                print(f"WARNING: judge output unparseable for {judge.parse_failures}/{len(res.rows)} examples", file=sys.stderr)
        path = res.save(args.out)
        print(path.read_text())
        return 0

    base, cand = RunResult.load(args.out, args.baseline), RunResult.load(args.out, args.candidate)
    deltas, failures = compare(base, cand)
    md = render_markdown(base, cand, deltas, failures)
    print(md)
    if args.report:
        args.report.write_text(md)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
