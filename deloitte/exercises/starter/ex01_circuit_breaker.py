"""Exercise 01: circuit breaker state machine.          (concept: 01-agent-runtime/LEARN.md)

A circuit breaker stops calling a dependency that keeps failing, so a dead
tool costs microseconds instead of a timeout on every request.

    closed --(failure_threshold consecutive failures)--> open
    open   --(reset_timeout seconds pass)--------------> half_open
    half_open --(next call succeeds)--> closed
    half_open --(next call fails)----> open   (immediately, timer restarts)

Rules:
* `state` returns "closed", "open" or "half_open" (computed from the clock).
* `call(fn)` raises CircuitOpen without calling fn while open.
* A success resets the failure count.
* Use `self.clock()` for time, never time.time(), so tests can control it.

Run:  make check EX=01
"""


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_timeout: float, clock):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.clock = clock
        # TODO: whatever state you need

    @property
    def state(self) -> str:
        raise NotImplementedError

    def call(self, fn):
        raise NotImplementedError
