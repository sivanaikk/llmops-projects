"""Reference solution for exercise 01 (same design as agentops/resilience.py)."""


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_timeout: float, clock):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.clock = clock
        self.failures = 0
        self.opened_at = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.reset_timeout else "open"

    def call(self, fn):
        state = self.state
        if state == "open":
            raise CircuitOpen()
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if state == "half_open" or self.failures >= self.failure_threshold:
                self.opened_at = self.clock()
            raise
        self.failures = 0
        self.opened_at = None
        return result
