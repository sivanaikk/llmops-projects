"""PII detection and redaction.

Regex-first on purpose: it runs inline on every gateway request, so it has to
be fast (microseconds, not a model call) and deterministic. A model-based
detector (e.g. Presidio + spaCy) can be layered on later for names/addresses,
but the high-risk structured identifiers are all caught here.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Verhoeff checksum tables (used by Aadhaar numbers).
_V_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_V_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def _verhoeff_ok(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


@dataclass(frozen=True)
class PiiRule:
    entity: str
    pattern: re.Pattern
    validator: Callable[[str], bool] | None = None  # optional post-match check to cut false positives


RULES: list[PiiRule] = [
    PiiRule("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    PiiRule(
        "CREDIT_CARD",
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
        validator=lambda m: _luhn_ok(re.sub(r"\D", "", m)),
    ),
    PiiRule("US_SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    PiiRule("IN_PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    PiiRule(
        "IN_AADHAAR",
        re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"),
        # Without the checksum, any 12 digits starting 2-9 match, e.g. part of an order number.
        validator=lambda m: _verhoeff_ok(re.sub(r"\D", "", m)),
    ),
    PiiRule(
        "PHONE",
        re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\w)"),
    ),
    PiiRule("IPV4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    PiiRule("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    PiiRule("API_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
]


@dataclass
class PiiFinding:
    entity: str
    start: int
    end: int
    text: str


@dataclass
class RedactionResult:
    text: str
    findings: list[PiiFinding] = field(default_factory=list)

    @property
    def entities(self) -> set[str]:
        return {f.entity for f in self.findings}


def detect(text: str, rules: list[PiiRule] = RULES) -> list[PiiFinding]:
    """Return non-overlapping findings, earliest rule wins on overlap."""
    findings: list[PiiFinding] = []
    taken: list[tuple[int, int]] = []
    for rule in rules:
        for m in rule.pattern.finditer(text):
            if rule.validator and not rule.validator(m.group(0)):
                continue
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            taken.append((s, e))
            findings.append(PiiFinding(rule.entity, s, e, m.group(0)))
    return sorted(findings, key=lambda f: f.start)


def _token(entity: str, value: str, salt: str) -> str:
    # Stable pseudonym: the same email maps to the same token within a request,
    # so the model can still reason about "the same person" without seeing them.
    digest = hashlib.sha256((salt + value).encode()).hexdigest()[:8]
    return f"<{entity}_{digest}>"


def redact(text: str, salt: str = "", rules: list[PiiRule] = RULES) -> RedactionResult:
    findings = detect(text, rules)
    out, cursor = [], 0
    for f in findings:
        out.append(text[cursor : f.start])
        out.append(_token(f.entity, f.text, salt))
        cursor = f.end
    out.append(text[cursor:])
    return RedactionResult("".join(out), findings)
