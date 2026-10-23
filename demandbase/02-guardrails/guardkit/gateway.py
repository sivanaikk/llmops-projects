"""Apply guardkit policies to OpenAI-format chat requests/responses.

Kept free of LiteLLM imports so it can be unit-tested and reused by any
gateway; `01-llm-gateway/custom_guardrail.py` is the thin LiteLLM adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .policy import Action, Policy, check_input, check_output


class GuardrailBlocked(Exception):
    def __init__(self, reasons: list[str], policy: str):
        self.reasons = reasons
        self.policy = policy
        super().__init__(f"request blocked by guardrail policy '{policy}': {', '.join(reasons)}")


@dataclass
class RequestReport:
    policy: str
    actions: list[str] = field(default_factory=list)
    pii_entities: set[str] = field(default_factory=set)
    max_injection_score: float = 0.0


def _text_parts(message: dict):
    """Yield (setter, text) for every text segment of a chat message."""
    content = message.get("content")
    if isinstance(content, str):
        yield (lambda v, m=message: m.__setitem__("content", v)), content
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                yield (lambda v, p=part: p.__setitem__("text", v)), part["text"]


def guard_request(data: dict, policy: Policy, salt: str = "") -> RequestReport:
    """Mutates `data["messages"]` in place (redaction) or raises GuardrailBlocked.

    Only user/tool messages are checked for injection: the system prompt is
    ours, and assistant turns were already checked on the way out.
    """
    report = RequestReport(policy.name)
    for msg in data.get("messages") or []:
        if msg.get("role") not in ("user", "tool"):
            continue
        for set_text, text in _text_parts(msg):
            d = check_input(text, policy, salt=salt)
            report.max_injection_score = max(report.max_injection_score, d.injection_score)
            report.pii_entities |= d.pii_entities
            if d.action is Action.BLOCK:
                raise GuardrailBlocked(d.reasons, policy.name)
            if d.action is Action.REDACT:
                set_text(d.text)
                report.actions.extend(d.reasons)
    return report


def guard_response_text(text: str, policy: Policy, salt: str = "") -> tuple[str, list[str]]:
    d = check_output(text, policy, salt=salt)
    if d.action is Action.BLOCK:
        raise GuardrailBlocked(d.reasons, policy.name)
    return d.text, d.reasons
