"""python -m agentops "Is payments-api healthy, and can we deploy to it today?" """

import json
import sys

from .agent import Agent
from .builtin_tools import default_tools
from .llm import OpenAICompatClient
from .tools import ToolRegistry

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Is payments-api healthy, and can we deploy to it today?"
    r = Agent(OpenAICompatClient(), ToolRegistry(default_tools())).run(q)
    print(r.answer)
    print(json.dumps({"outcome": r.outcome, "steps": r.steps, "tools": [c.tool for c in r.tool_calls],
                      "cost_usd": round(r.cost_usd, 6), "duration_s": round(r.duration_s, 2)}, indent=2))
