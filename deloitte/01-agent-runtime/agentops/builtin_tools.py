"""Incident-desk tools: read-only lookups over a fictional service catalogue
and runbook library, plus a safe calculator."""

from __future__ import annotations

import ast
import json
import operator
import re
from pathlib import Path

from .tools import Tool, ToolError

DATA = Path(__file__).resolve().parents[1] / "data"


def _catalogue() -> dict:
    return json.loads((DATA / "services.json").read_text())["services"]


def get_service_status(service: str) -> dict:
    svc = _catalogue().get(service)
    if svc is None:
        raise ToolError("not_found", f"no service named '{service}'. Known: {', '.join(_catalogue())}")
    return {k: svc[k] for k in ("owner", "tier", "status", "p95_latency_ms", "open_incident", "last_deploy")}


def get_error_budget(service: str) -> dict:
    svc = _catalogue().get(service)
    if svc is None:
        raise ToolError("not_found", f"no service named '{service}'")
    remaining = svc["error_budget_remaining"]
    return {
        "slo_availability": svc["slo_availability"],
        "error_budget_remaining": remaining,
        "release_gate": "open" if remaining > 0.1 else ("restricted" if remaining > 0 else "frozen"),
    }


def search_runbooks(query: str) -> list[dict]:
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for path in sorted((DATA / "runbooks").glob("*.md")):
        text = path.read_text()
        tags = set(re.findall(r"[a-z0-9]+", text.split("\n", 2)[1].lower())) if "Tags:" in text else set()
        body = set(re.findall(r"[a-z0-9]+", text.lower()))
        score = 3 * len(words & tags) + len(words & body)
        if score:
            scored.append((score, path.stem, text.split("\n", 1)[0].lstrip("# ").strip()))
    scored.sort(reverse=True)
    return [{"runbook": stem, "title": title} for _, stem, title in scored[:3]]


def read_runbook(name: str) -> str:
    path = DATA / "runbooks" / f"{name}.md"
    if not re.fullmatch(r"[a-z0-9-]+", name) or not path.exists():
        raise ToolError("not_found", f"no runbook '{name}'")
    return path.read_text()


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}


def calculator(expression: str) -> float:
    """Arithmetic only, via the AST: never eval() model output."""

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            if isinstance(node.op, ast.Pow) and abs(ev(node.right)) > 10:
                raise ToolError("bad_args", "exponent too large")
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ToolError("bad_args", "only arithmetic is allowed")

    if len(expression) > 200:
        raise ToolError("bad_args", "expression too long")
    try:
        return round(float(ev(ast.parse(expression, mode="eval").body)), 6)
    except (SyntaxError, ZeroDivisionError) as e:
        raise ToolError("bad_args", str(e)) from e


def default_tools() -> list[Tool]:
    return [
        Tool("get_service_status", "current status, owner, latency and open incident of a service", {"service": "string"},
             get_service_status, timeout_s=2),
        Tool("get_error_budget", "SLO and remaining error budget (fraction, negative = overspent) and release gate state",
             {"service": "string"}, get_error_budget, timeout_s=2),
        Tool("search_runbooks", "find runbooks relevant to a symptom", {"query": "string"}, search_runbooks, timeout_s=2),
        Tool("read_runbook", "read a runbook by name (from search_runbooks)", {"name": "string"}, read_runbook, timeout_s=2),
        Tool("calculator", "evaluate an arithmetic expression", {"expression": "string"}, calculator, timeout_s=1),
    ]
