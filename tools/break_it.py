"""Break it on purpose: inject a realistic bug and see which safeguard catches it.

Every safeguard in these labs (a test, an alert rule, a policy check) exists
because of a failure that happens in real systems. This tool makes that
concrete: it copies a lab to a temporary directory, applies one mutation
(a small, plausible bug), and runs the check that is supposed to catch it.
Your working tree is never modified.

    python tools/break_it.py deloitte --list
    python tools/break_it.py deloitte --show agent-no-loop-detection   # the diff, without running
    python tools/break_it.py deloitte --run agent-no-loop-detection    # inject + run the check
    python tools/break_it.py deloitte --all                            # CI: every mutation must be caught

Try it yourself first: read the mutation, predict which test or alert fails and
why, then --run it.
"""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache", ".terraform", "results", "mlruns", "*.db")


def load(lab: str) -> list[dict]:
    return yaml.safe_load((ROOT / lab / "break-it.yaml").read_text())["mutations"]


def requirements_met(m: dict) -> str | None:
    for tool in m.get("needs", []):
        if shutil.which(tool) is None:
            return f"needs `{tool}` on PATH"
    return None


def command(check: str) -> str:
    # Run pytest with the same interpreter as this tool.
    return check.replace("pytest ", f'"{sys.executable}" -m pytest -p no:cacheprovider ', 1) if check.startswith("pytest ") else check


def run_check(workdir: Path, check: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(command(check), shell=True, cwd=workdir, env=env, capture_output=True, text=True, timeout=600, check=False)


def mutate(workdir: Path, m: dict) -> str:
    path = workdir / m["file"]
    text = path.read_text()
    count = text.count(m["find"])
    if count != 1:
        raise SystemExit(f"[{m['id']}] `find` text occurs {count} times in {m['file']} (must be exactly 1): update break-it.yaml")
    new = text.replace(m["find"], m["replace"])
    path.write_text(new)
    return "".join(difflib.unified_diff(text.splitlines(True), new.splitlines(True), f"a/{m['file']}", f"b/{m['file']}"))


def diff_only(lab: str, m: dict) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / lab
        shutil.copytree(ROOT / lab, work, ignore=IGNORE)
        return mutate(work, m)


def run(lab: str, m: dict, verbose: bool = True) -> str:
    """Returns 'caught', 'survived' or 'skipped: reason'."""
    reason = requirements_met(m)
    if reason:
        return f"skipped: {reason}"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / lab
        shutil.copytree(ROOT / lab, work, ignore=IGNORE)
        clean = run_check(work, m["check"])
        if clean.returncode != 0:
            print(clean.stdout[-2000:], clean.stderr[-2000:])
            raise SystemExit(f"[{m['id']}] the check fails even WITHOUT the mutation: fix the lab first")
        diff = mutate(work, m)
        res = run_check(work, m["check"])
    caught = res.returncode != 0
    if verbose:
        print(f"\n=== {m['id']}: {m['title']}\n")
        print(diff)
        print(f"$ {m['check']}")
        tail = (res.stdout + res.stderr).strip().splitlines()
        print("\n".join(line for line in tail if any(k in line for k in ("FAIL", "Error", "assert", "passed", "failed", "---", "SUCCESS")))[-3000:])
        print(f"\nresult: {'CAUGHT' if caught else 'SURVIVED (the safeguard missed it!)'}")
        print(f"\nwhy it matters: {m['lesson'].strip()}\n")
    return "caught" if caught else "survived"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="break_it")
    ap.add_argument("lab", choices=["deloitte", "demandbase"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--show", metavar="ID")
    g.add_argument("--run", metavar="ID")
    g.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    mutations = load(args.lab)
    by_id = {m["id"]: m for m in mutations}

    if args.list:
        width = max(len(m["id"]) for m in mutations)
        for m in mutations:
            print(f"  {m['id']:<{width}}  [{m['project']}] {m['title']}")
        return 0
    if args.show:
        m = by_id[args.show]
        print(f"{m['title']}\n\n{diff_only(args.lab, m)}\ncheck: {m['check']}\n\nPredict: which test or alert fails, and why?")
        return 0
    if args.run:
        return 0 if run(args.lab, by_id[args.run]) == "caught" else 1

    results = {}
    for m in mutations:
        results[m["id"]] = run(args.lab, m, verbose=False)
        print(f"  {results[m['id']]:<10} {m['id']}", flush=True)
    survived = [k for k, v in results.items() if v == "survived"]
    print(f"\n{sum(v == 'caught' for v in results.values())} caught, {len(survived)} survived, "
          f"{sum(v.startswith('skipped') for v in results.values())} skipped")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
