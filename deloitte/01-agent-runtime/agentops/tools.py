"""Tool registry: every tool call is validated, time-boxed, circuit-broken and,
only when the tool is idempotent, retried."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any

from .resilience import CircuitBreaker, CircuitOpen, Deadline, retry_call

_TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool}


class ToolError(Exception):
    """A tool failed; `kind` is a bounded label safe to use in metrics."""

    def __init__(self, kind: str, msg: str):
        self.kind = kind
        super().__init__(msg)


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, str]  # arg name -> json type
    fn: Callable[..., Any]
    timeout_s: float = 5.0
    idempotent: bool = True  # read-only tools may be retried; side-effecting ones may not
    required: list[str] = field(default_factory=list)

    def spec(self) -> str:
        args = ", ".join(f"{k}: {v}" for k, v in self.params.items())
        return f"- {self.name}({args}): {self.description}"


class ToolRegistry:
    def __init__(self, tools: list[Tool], breaker_threshold: int = 3, breaker_reset_s: float = 30.0):
        self.tools = {t.name: t for t in tools}
        self.breakers = {t.name: CircuitBreaker(t.name, breaker_threshold, breaker_reset_s) for t in tools}
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")

    def describe(self) -> str:
        return "\n".join(t.spec() for t in self.tools.values())

    def validate(self, name: str, args: Any) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError("unknown_tool", f"unknown tool '{name}'. Available: {', '.join(self.tools)}")
        if not isinstance(args, dict):
            raise ToolError("bad_args", "args must be a JSON object")
        missing = [k for k in (tool.required or tool.params) if k not in args]
        if missing:
            raise ToolError("bad_args", f"missing args for {name}: {missing}")
        extra = [k for k in args if k not in tool.params]
        if extra:
            raise ToolError("bad_args", f"unexpected args for {name}: {extra}")
        for k, v in args.items():
            if not isinstance(v, _TYPES[tool.params[k]]) or (tool.params[k] == "number" and isinstance(v, bool)):
                raise ToolError("bad_args", f"arg {k} must be {tool.params[k]}")
        return args

    def call(self, name: str, args: Any, deadline: Deadline | None = None) -> Any:
        args = self.validate(name, args)
        tool = self.tools[name]

        def once():
            timeout = deadline.cap(tool.timeout_s) if deadline else tool.timeout_s
            fut = self._pool.submit(tool.fn, **args)
            try:
                return fut.result(timeout=timeout)
            except FutureTimeout as e:
                fut.cancel()
                raise ToolError("timeout", f"{name} timed out after {timeout:.1f}s") from e
            except ToolError:
                raise
            except Exception as e:  # tool bug or dependency failure
                raise ToolError("error", f"{name} failed: {e}") from e

        def guarded():
            return self.breakers[name].call(once)

        try:
            if tool.idempotent:
                return retry_call(guarded, attempts=2, base_delay=0.1, retry_on=(ToolError,), deadline=deadline)
            return guarded()
        except CircuitOpen as e:
            raise ToolError("circuit_open", str(e)) from e
