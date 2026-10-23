"""Resilience primitives for agent workloads: retry, circuit breaker, deadline.

Agents multiply dependency calls (one user request -> N model calls + M tool
calls), so a flaky dependency turns into a slow, expensive, failing request
unless every hop is bounded. These are the bounds.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


class DeadlineExceeded(Exception):
    pass


class CircuitOpen(Exception):
    def __init__(self, name: str, retry_in: float):
        self.name, self.retry_in = name, retry_in
        super().__init__(f"circuit '{name}' open; retry in {retry_in:.1f}s")


@dataclass
class Deadline:
    """Wall-clock budget for a whole agent run, shared by every hop inside it."""

    seconds: float
    clock: Callable[[], float] = time.monotonic
    started: float = field(default=0.0)

    def __post_init__(self):
        self.started = self.clock()

    @property
    def remaining(self) -> float:
        return self.seconds - (self.clock() - self.started)

    def check(self) -> None:
        if self.remaining <= 0:
            raise DeadlineExceeded(f"run exceeded {self.seconds:.1f}s deadline")

    def cap(self, timeout: float) -> float:
        """Never let a single hop wait longer than the run has left."""
        return max(0.001, min(timeout, self.remaining))


def retry_call(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    deadline: Deadline | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    """Exponential backoff with full jitter (avoids synchronized retry storms)."""
    rng = rng or random.Random()
    for attempt in range(1, attempts + 1):
        if deadline:
            deadline.check()
        try:
            return fn()
        except retry_on:
            if attempt == attempts:
                raise
            delay = rng.uniform(0, min(max_delay, base_delay * 2 ** (attempt - 1)))
            if deadline:
                delay = min(delay, max(0.0, deadline.remaining))
            sleep(delay)
    raise AssertionError("unreachable")


class CircuitBreaker:
    """closed -> (N consecutive failures) -> open -> (reset_timeout) -> half-open -> closed|open"""

    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 30.0, clock=time.monotonic):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state()

    def _state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self.clock() - self._opened_at >= self.reset_timeout:
            return "half_open"
        return "open"

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            state = self._state()
            if state == "open":
                raise CircuitOpen(self.name, self.reset_timeout - (self.clock() - self._opened_at))
        try:
            result = fn()
        except Exception:
            with self._lock:
                self._failures += 1
                # A failed probe in half-open re-opens immediately.
                if state == "half_open" or self._failures >= self.failure_threshold:
                    self._opened_at = self.clock()
            raise
        with self._lock:
            self._failures = 0
            self._opened_at = None
        return result
