"""Scorers: each takes (example, output) and returns a score in [0, 1].

Deterministic scorers run first and are the gate; the LLM judge adds signal
on qualities string matching can't see (faithfulness) and is itself checked
against a small human-labelled calibration set before anyone trusts it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

ABSTAIN = re.compile(r"\b(don'?t|do not|cannot|can't) know\b|\bnot (in|mentioned in|available in) the (account )?notes\b", re.I)


@dataclass
class Example:
    id: str
    question: str
    must_include: list[str]
    source: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def answerable(self) -> bool:
        return self.source is not None


@dataclass
class Output:
    answer: str
    contexts: list[str]
    sources: list[str]
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None


class Scorer(Protocol):
    name: str

    def __call__(self, ex: Example, out: Output) -> float: ...


def abstained(text: str) -> bool:
    return bool(ABSTAIN.search(text.replace("’", "'")))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


class FactRecall:
    """Share of required facts present in the answer (case/whitespace-insensitive)."""

    name = "fact_recall"

    def __call__(self, ex: Example, out: Output) -> float:
        if not ex.answerable:
            return 1.0 if abstained(out.answer) else 0.0
        a = _norm(out.answer)
        return sum(1 for f in ex.must_include if _norm(f) in a) / len(ex.must_include)


class RetrievalHit:
    """Did retrieval surface the gold chunk? Separates retrieval bugs from generation bugs."""

    name = "retrieval_hit"

    def __call__(self, ex: Example, out: Output) -> float:
        if not ex.answerable:
            return 1.0
        return 1.0 if ex.source in out.sources else 0.0


class Abstention:
    """Penalise hallucinating on unanswerable questions and refusing answerable ones."""

    name = "abstention_correct"

    def __call__(self, ex: Example, out: Output) -> float:
        return 1.0 if abstained(out.answer) == (not ex.answerable) else 0.0


class Concise:
    name = "concise"

    def __init__(self, max_words: int = 80):
        self.max_words = max_words

    def __call__(self, ex: Example, out: Output) -> float:
        return 1.0 if len(out.answer.split()) <= self.max_words else 0.0


JUDGE_PROMPT = """You are grading an AI assistant's answer for faithfulness.
Context the assistant was given:
<context>
{context}
</context>
Question: {question}
Answer: {answer}

Is every factual claim in the answer supported by the context? An answer that
correctly says it doesn't know is fully faithful.
Respond with JSON only: {{"score": <1-5 integer>, "reason": "<one sentence>"}}
where 5 = fully supported, 1 = mostly unsupported or contradicted."""


class LLMJudgeFaithfulness:
    """LLM-as-judge via the gateway `judge` model (qwen2.5:1.5b by default)."""

    name = "judge_faithfulness"

    def __init__(self, chat: Callable[[list[dict]], str]):
        self.chat = chat
        self.parse_failures = 0

    def __call__(self, ex: Example, out: Output) -> float:
        prompt = JUDGE_PROMPT.format(context="\n\n".join(out.contexts)[:6000], question=ex.question, answer=out.answer)
        raw = self.chat([{"role": "user", "content": prompt}])
        score = parse_judge_score(raw)
        if score is None:
            self.parse_failures += 1
            return 0.0
        return (score - 1) / 4


def parse_judge_score(raw: str) -> int | None:
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            s = int(json.loads(m.group(0)).get("score"))
            return s if 1 <= s <= 5 else None
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    m = re.search(r"score\"?\s*[:=]\s*([1-5])", raw)
    return int(m.group(1)) if m else None


DEFAULT_SCORERS: list[Scorer] = [FactRecall(), RetrievalHit(), Abstention(), Concise()]
