"""Per-team guardrail policy and the decision engine the gateway hook calls.

Policies live in YAML so a product team can tighten or relax them via a merge
request instead of a gateway code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

from . import injection, pii


class Action(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass
class Policy:
    name: str = "default"
    pii_action: Action = Action.REDACT  # what to do with PII in prompts
    block_pii_entities: set[str] = field(default_factory=lambda: {"US_SSN", "CREDIT_CARD", "AWS_ACCESS_KEY", "API_KEY"})
    injection_threshold: float = 0.5
    max_input_chars: int = 32_000
    denied_topics: list[str] = field(default_factory=list)
    output_pii_action: Action = Action.REDACT

    @classmethod
    def from_dict(cls, name: str, d: dict) -> Policy:
        return cls(
            name=name,
            pii_action=Action(d.get("pii_action", "redact")),
            block_pii_entities=set(d.get("block_pii_entities", cls().block_pii_entities)),
            injection_threshold=float(d.get("injection_threshold", 0.5)),
            max_input_chars=int(d.get("max_input_chars", 32_000)),
            denied_topics=list(d.get("denied_topics", [])),
            output_pii_action=Action(d.get("output_pii_action", "redact")),
        )


def load_policies(path: str | Path) -> dict[str, Policy]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return {name: Policy.from_dict(name, d or {}) for name, d in raw.get("policies", {}).items()}


@dataclass
class Decision:
    action: Action
    text: str
    reasons: list[str] = field(default_factory=list)
    pii_entities: set[str] = field(default_factory=set)
    injection_score: float = 0.0


def check_input(text: str, policy: Policy, salt: str = "") -> Decision:
    reasons: list[str] = []

    if len(text) > policy.max_input_chars:
        return Decision(Action.BLOCK, text, [f"input_too_long:{len(text)}"])

    for topic in policy.denied_topics:
        if re.search(rf"\b{re.escape(topic)}\b", text, re.I):
            return Decision(Action.BLOCK, text, [f"denied_topic:{topic}"])

    verdict = injection.score(text)
    if verdict.is_attack(policy.injection_threshold):
        return Decision(
            Action.BLOCK, text, [f"prompt_injection:{','.join(verdict.matched)}"], injection_score=verdict.score
        )

    red = pii.redact(text, salt=salt)
    hard = red.entities & policy.block_pii_entities
    if hard:
        return Decision(Action.BLOCK, text, [f"pii_blocked:{','.join(sorted(hard))}"], red.entities, verdict.score)
    if red.findings and policy.pii_action is Action.BLOCK:
        return Decision(Action.BLOCK, text, ["pii_present"], red.entities, verdict.score)
    if red.findings and policy.pii_action is Action.REDACT:
        reasons.append(f"pii_redacted:{','.join(sorted(red.entities))}")
        return Decision(Action.REDACT, red.text, reasons, red.entities, verdict.score)

    return Decision(Action.ALLOW, text, reasons, red.entities, verdict.score)


def check_output(text: str, policy: Policy, salt: str = "") -> Decision:
    red = pii.redact(text, salt=salt)
    if not red.findings or policy.output_pii_action is Action.ALLOW:
        return Decision(Action.ALLOW, text, pii_entities=red.entities)
    if policy.output_pii_action is Action.BLOCK:
        return Decision(Action.BLOCK, text, ["output_pii"], red.entities)
    return Decision(Action.REDACT, red.text, [f"output_pii_redacted:{','.join(sorted(red.entities))}"], red.entities)
