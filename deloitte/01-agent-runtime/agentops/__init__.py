"""agentops: a bounded, observable tool-using agent runtime for small models."""

from .agent import OUTCOMES, Agent, AgentConfig, RunResult, parse_action
from .builtin_tools import default_tools
from .llm import LLMError, OpenAICompatClient, ScriptedLLM
from .telemetry import Telemetry
from .tools import Tool, ToolError, ToolRegistry

__all__ = ["OUTCOMES", "Agent", "AgentConfig", "RunResult", "parse_action", "default_tools", "LLMError",
           "OpenAICompatClient", "ScriptedLLM", "Telemetry", "Tool", "ToolError", "ToolRegistry"]
