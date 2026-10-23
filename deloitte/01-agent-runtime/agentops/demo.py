"""Watch the agent loop step by step, no model needed.

    python -m agentops.demo                 # all scenarios
    python -m agentops.demo loop            # one scenario

Each scenario replays scripted model replies through the real Agent, tools,
guards and telemetry, and prints what happened at every step: the model's
action, the tool result, and which safeguard fired. It's the fastest way to
see why each bound in agent.py exists.
"""

from __future__ import annotations

import json
import sys

from .agent import Agent, AgentConfig
from .builtin_tools import default_tools
from .llm import LLMError, ScriptedLLM
from .telemetry import Telemetry
from .tools import ToolRegistry


def act(action: str, **kw) -> str:
    return json.dumps({"thought": kw.pop("thought", ""), "action": action, **kw})


SCENARIOS = {
    "happy": (
        "Is payments-api healthy, and can we ship a feature to it?",
        [act("get_service_status", thought="check status first", args={"service": "payments-api"}),
         act("get_error_budget", thought="now the release gate", args={"service": "payments-api"}),
         act("final", answer="payments-api is degraded (INC-1042) but has 18% error budget left: release gate open.")],
        "Two grounded lookups, then an answer that quotes them.",
    ),
    "recover": (
        "What's the status of LLM gateway?",
        [act("get_service_status", args={"service": "llm gateway service"}),
         act("get_service_status", args={"service": "llm-gateway"}),
         act("final", answer="llm-gateway is healthy.")],
        "A tool error goes back to the model as an observation, and it corrects itself.",
    ),
    "loop": (
        "Which runbook covers latency?",
        [act("search_runbooks", args={"query": "latency"})] * 6,
        "The model repeats an identical call; loop detection stops it on the 3rd repeat.",
    ),
    "invalid": (
        "Who owns search-api?",
        ["Sure! search-api is owned by team-discovery :)"] * 4,
        "The model ignores the JSON protocol; it gets corrective re-prompts, then the run stops cleanly.",
    ),
    "provider-down": (
        "Is auth-service healthy?",
        [LLMError("503 from provider", retryable=True)] * 5,
        "Retryable errors are retried with backoff, then the run ends as llm_unavailable (no hang, no crash).",
    ),
    "change-request": (
        "Delete the payments-api deployment now.",
        [act("final", answer="The payments-api deployment has been deleted.")],
        "Refused in code before the model is called; the scripted false claim is never even reached.",
    ),
    "false-claim": (
        "payments-api looks broken, sort it out",
        [act("final", answer="I have restarted payments-api, it is fine now.")],
        "The model claims an action it has no tool for; the post-check replaces the answer.",
    ),
}


class Narrator(ScriptedLLM):
    def complete(self, messages, timeout, max_tokens):
        step = len(self.calls) + 1
        last = messages[-1]["content"] if len(messages) > 2 else None
        if last:
            print(f"    observation: {last[:110]}")
        try:
            res = super().complete(messages, timeout, max_tokens)
        except LLMError as e:
            print(f"  step {step}: model call failed ({e}, retryable={e.retryable})")
            raise
        print(f"  step {step}: model -> {res.text[:110]}")
        return res


def run(name: str) -> None:
    question, script, point = SCENARIOS[name]
    tm = Telemetry()
    agent = Agent(Narrator(script), ToolRegistry(default_tools()), AgentConfig(), tm, sleep=lambda s: None)
    print(f"\n### {name}: {question!r}")
    r = agent.run(question)
    guards = {s.labels["action"]: s.value for m in tm.registry.collect() if m.name == "agent_guard_actions"
              for s in m.samples if s.name.endswith("_total")}
    print(f"  => outcome={r.outcome} steps={r.steps} tools={[c.tool for c in r.tool_calls]} "
          f"cost=${r.cost_usd:.6f}" + (f" guards={guards}" if guards else ""))
    print(f"  => answer: {r.answer[:140]}")
    print(f"  lesson: {point}")


def main(argv: list[str]) -> int:
    names = argv or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s) {unknown}; choose from {', '.join(SCENARIOS)}")
        return 2
    for n in names:
        run(n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
