"""Heuristic prompt-injection / jailbreak scoring.

A weighted signal list rather than a classifier: cheap enough to run on every
request at the gateway, explainable in an incident review ("it matched
`ignore_previous`"), and tunable per team via the threshold. Teams that need
more can add a small classifier model behind the same `score()` interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SIGNALS: dict[str, tuple[re.Pattern, float]] = {
    "ignore_previous": (
        re.compile(r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier|all)\b.{0,20}\b(instructions?|rules|prompts?)\b", re.I),
        0.6,
    ),
    "reveal_system_prompt": (
        re.compile(r"\b(reveal|print|show|repeat|output)\b.{0,30}\b(system|hidden|initial)\s+(prompt|instructions?|message)\b", re.I),
        0.6,
    ),
    "role_override": (
        re.compile(r"\byou are (now|no longer)\b|\bact as (an? )?(unfiltered|unrestricted|jailbroken)\b|\bDAN\b|developer mode", re.I),
        0.5,
    ),
    "policy_bypass": (
        re.compile(r"\b(bypass|disable|turn off|override)\b.{0,20}\b(safety|guardrails?|filters?|restrictions?|policy)\b", re.I),
        0.5,
    ),
    "delimiter_spoof": (
        re.compile(r"<\|?(im_start|im_end|system|endoftext)\|?>|\[/?INST\]|###\s*system", re.I),
        0.4,
    ),
    "exfil_markdown_image": (
        re.compile(r"!\[[^\]]*\]\(https?://[^)]*\{?[^)]*\)", re.I),
        0.3,
    ),
}


@dataclass
class InjectionVerdict:
    score: float
    matched: list[str]

    def is_attack(self, threshold: float) -> bool:
        return self.score >= threshold


def score(text: str) -> InjectionVerdict:
    matched = [name for name, (pat, _) in SIGNALS.items() if pat.search(text)]
    # Noisy-OR combination: independent weak signals add up but never exceed 1.
    p_clean = 1.0
    for name in matched:
        p_clean *= 1.0 - SIGNALS[name][1]
    return InjectionVerdict(round(1.0 - p_clean, 3), matched)
