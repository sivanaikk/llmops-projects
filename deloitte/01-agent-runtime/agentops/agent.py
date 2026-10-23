"""A bounded tool-using agent.

The failure modes that make agents hard to operate, and the bound on each:

| failure mode                         | bound                                         |
|--------------------------------------|-----------------------------------------------|
| loops forever / too many model calls | max_steps, loop detection on repeated actions |
| runaway spend                        | max_cost_usd, max_total_tokens per run        |
| hangs on a slow dependency           | run Deadline shared by every model/tool hop   |
| flaky model provider                 | retries on retryable errors only              |
| flaky tool                           | per-tool timeout + circuit breaker            |
| model breaks the output protocol     | parse/repair, corrective re-prompt, capped    |

Every run ends with an explicit `outcome` (never an unhandled exception), so
the outcome mix is a first-class SLI.

Protocol: small models are unreliable at native function calling, so the
model replies with one JSON object per step:
    {"thought": "...", "action": "<tool name>", "args": {...}}
    {"thought": "...", "action": "final", "answer": "..."}
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from .llm import LLMClient, LLMError
from .resilience import Deadline, DeadlineExceeded, retry_call
from .telemetry import Telemetry
from .tools import ToolError, ToolRegistry

OUTCOMES = ("success", "budget_steps", "budget_cost", "budget_tokens", "deadline", "loop_detected",
            "invalid_output", "llm_unavailable")

# USD per 1M tokens (input, output). Local models cost $0; shadow prices make
# cost anomalies and budget enforcement testable before a hosted model is used.
PRICES = {"qwen2.5:0.5b": (0.10, 0.40), "qwen2.5:1.5b": (0.20, 0.80), "scripted": (1.0, 2.0)}

SYSTEM = """You are an SRE incident-desk assistant. Use tools to look up facts; never guess service data.
Tools:
{tools}

Reply with exactly ONE JSON object and nothing else, either
{{"thought": "<short reasoning>", "action": "<tool name>", "args": {{...}}}}
or, when you have enough information,
{{"thought": "<short reasoning>", "action": "final", "answer": "<answer for the user>"}}"""


@dataclass
class AgentConfig:
    name: str = "incident-desk"
    max_steps: int = 6
    max_cost_usd: float = 0.01
    max_total_tokens: int = 12_000
    deadline_s: float = 60.0
    llm_timeout_s: float = 30.0
    max_output_tokens: int = 300
    max_invalid_outputs: int = 2
    loop_threshold: int = 2  # identical (tool, args) calls allowed before it's a loop


@dataclass
class ToolCall:
    tool: str
    args: dict
    ok: bool
    result: str
    error_kind: str | None = None
    latency_s: float = 0.0


@dataclass
class RunResult:
    run_id: str
    outcome: str
    answer: str
    steps: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0
    invalid_outputs: int = 0
    model: str = ""
    question_chars: int = 0

    def log_record(self, agent: str) -> dict:
        return {
            "ts": datetime.now(UTC).isoformat(),
            "agent": agent,
            "run_id": self.run_id,
            "model": self.model,
            "outcome": self.outcome,
            "steps": self.steps,
            "tools": [c.tool for c in self.tool_calls],
            "tool_errors": sum(1 for c in self.tool_calls if not c.ok),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": round(self.cost_usd, 8),
            "duration_s": round(self.duration_s, 4),
            "question_chars": self.question_chars,
            "answer_chars": len(self.answer),
            "invalid_outputs": self.invalid_outputs,
        }

    def to_dict(self) -> dict:
        return asdict(self)


def parse_action(text: str) -> dict:
    """Extract the first JSON object; tolerate code fences and chatter around it."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("reply must be an object with an 'action' field")
    if obj["action"] == "final" and not isinstance(obj.get("answer"), str):
        raise ValueError("final action needs a string 'answer'")
    return obj


def price(model: str, pt: int, ct: int) -> float:
    inp, out = PRICES.get(model, (0.0, 0.0))
    return (pt * inp + ct * out) / 1_000_000


FALLBACK = {
    "budget_steps": "I couldn't finish within the step limit. Partial findings: {partial}",
    "budget_cost": "I stopped to stay within the cost budget. Partial findings: {partial}",
    "budget_tokens": "I stopped to stay within the token budget. Partial findings: {partial}",
    "deadline": "I ran out of time. Partial findings: {partial}",
    "loop_detected": "I was repeating the same lookup, so I stopped. Partial findings: {partial}",
    "invalid_output": "I couldn't produce a well-formed answer. Partial findings: {partial}",
    "llm_unavailable": "The model service is unavailable right now; please retry shortly.",
}


class Agent:
    def __init__(self, llm: LLMClient, tools: ToolRegistry, config: AgentConfig | None = None,
                 telemetry: Telemetry | None = None, clock=time.monotonic, sleep=time.sleep):
        self.llm, self.tools = llm, tools
        self.sleep = sleep
        self.cfg = config or AgentConfig()
        self.tm = telemetry or Telemetry()
        self.clock = clock

    def _finish(self, r: RunResult, outcome: str, t0: float, answer: str | None = None) -> RunResult:
        r.outcome = outcome
        if answer is None:
            partial = "; ".join(f"{c.tool} -> {c.result[:120]}" for c in r.tool_calls if c.ok) or "none"
            answer = FALLBACK[outcome].format(partial=partial)
        r.answer = answer
        r.duration_s = self.clock() - t0
        self.tm.record_run(self.cfg.name, r)
        return r

    def run(self, question: str) -> RunResult:
        cfg, tm = self.cfg, self.tm
        t0 = self.clock()
        deadline = Deadline(cfg.deadline_s, clock=self.clock)
        r = RunResult(run_id=str(uuid.uuid4()), outcome="", answer="", model=self.llm.model, question_chars=len(question))
        messages = [{"role": "system", "content": SYSTEM.format(tools=self.tools.describe())},
                    {"role": "user", "content": question}]
        seen: dict[str, int] = {}

        with tm.span("agent.run", **{"agent.name": cfg.name, "gen_ai.request.model": self.llm.model}) as run_span:
            while True:
                if r.steps >= cfg.max_steps:
                    return self._finish(r, "budget_steps", t0)
                if r.cost_usd >= cfg.max_cost_usd:
                    return self._finish(r, "budget_cost", t0)
                if r.prompt_tokens + r.completion_tokens >= cfg.max_total_tokens:
                    return self._finish(r, "budget_tokens", t0)
                if deadline.remaining <= 0:
                    return self._finish(r, "deadline", t0)
                r.steps += 1

                with tm.span("agent.step", **{"agent.step": r.steps}) as step_span:
                    try:
                        res = self._call_llm(messages, deadline)
                    except DeadlineExceeded:
                        return self._finish(r, "deadline", t0)
                    except LLMError:
                        return self._finish(r, "llm_unavailable", t0)

                    r.prompt_tokens += res.prompt_tokens
                    r.completion_tokens += res.completion_tokens
                    r.cost_usd += price(res.model if res.model in PRICES else self.llm.model,
                                        res.prompt_tokens, res.completion_tokens)
                    step_span.set_attribute("gen_ai.usage.input_tokens", res.prompt_tokens)
                    step_span.set_attribute("gen_ai.usage.output_tokens", res.completion_tokens)
                    messages.append({"role": "assistant", "content": res.text})

                    try:
                        action = parse_action(res.text)
                    except ValueError as e:
                        r.invalid_outputs += 1
                        tm.invalid_outputs.labels(cfg.name).inc()
                        if r.invalid_outputs > cfg.max_invalid_outputs:
                            return self._finish(r, "invalid_output", t0)
                        messages.append({"role": "user", "content": f"Invalid reply ({e}). Reply with ONE JSON object "
                                                                    "following the protocol."})
                        continue

                    if action["action"] == "final":
                        run_span.set_attribute("agent.outcome", "success")
                        return self._finish(r, "success", t0, action["answer"].strip())

                    name, args = str(action["action"]), action.get("args", {})
                    key = f"{name}:{json.dumps(args, sort_keys=True)}"
                    seen[key] = seen.get(key, 0) + 1
                    if seen[key] > cfg.loop_threshold:
                        return self._finish(r, "loop_detected", t0)

                    try:
                        observation = self._call_tool(r, name, args, deadline)
                    except DeadlineExceeded:
                        return self._finish(r, "deadline", t0)
                    messages.append({"role": "user", "content": f"Observation from {name}: {observation}"})

    def _call_llm(self, messages, deadline):
        def once():
            return self.llm.complete(messages, timeout=deadline.cap(self.cfg.llm_timeout_s),
                                     max_tokens=self.cfg.max_output_tokens)

        def retryable_once():
            try:
                return once()
            except LLMError as e:
                self.tm.llm_errors.labels(self.cfg.name, str(e.retryable).lower()).inc()
                if e.retryable:
                    raise LLMRetryable(e) from e
                raise

        try:
            return retry_call(retryable_once, attempts=3, base_delay=0.5, retry_on=(LLMRetryable,), deadline=deadline,
                              sleep=self.sleep)
        except LLMRetryable as e:
            raise e.inner from e

    def _call_tool(self, r: RunResult, name: str, args, deadline: Deadline) -> str:
        t = self.clock()
        with self.tm.span("agent.tool", **{"agent.tool.name": name if name in self.tools.tools else "unknown"}) as s:
            try:
                out = self.tools.call(name, args, deadline=deadline)
                text = out if isinstance(out, str) else json.dumps(out)
                text = text[:2000]  # keep observations from blowing the context window
                r.tool_calls.append(ToolCall(name, args if isinstance(args, dict) else {}, True, text, None, self.clock() - t))
                self.tm.tool_calls.labels(self.cfg.name, name, "ok").inc()
                return text
            except DeadlineExceeded:
                raise
            except ToolError as e:
                s.set_attribute("error.type", e.kind)
                label = name if name in self.tools.tools else "unknown"
                r.tool_calls.append(ToolCall(name, args if isinstance(args, dict) else {}, False, str(e), e.kind,
                                             self.clock() - t))
                self.tm.tool_calls.labels(self.cfg.name, label, e.kind).inc()
                # Errors go back to the model as observations so it can recover (e.g. fix a service name).
                return f"ERROR ({e.kind}): {e}"


class LLMRetryable(Exception):
    def __init__(self, inner: LLMError):
        self.inner = inner
        super().__init__(str(inner))
