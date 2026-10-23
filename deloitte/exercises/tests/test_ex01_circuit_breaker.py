import pytest


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def boom():
    raise RuntimeError("dependency down")


@pytest.fixture
def m(impl):
    return impl("ex01_circuit_breaker")


def test_starts_closed_and_passes_results_through(m):
    cb = m.CircuitBreaker(3, 10, Clock())
    assert cb.state == "closed" and cb.call(lambda: 42) == 42


def test_opens_after_threshold_and_stops_calling(m):
    clock, calls = Clock(), []
    cb = m.CircuitBreaker(2, 10, clock)

    def failing():
        calls.append(1)
        raise RuntimeError

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(failing)
    assert cb.state == "open"
    with pytest.raises(m.CircuitOpen):
        cb.call(failing)
    assert len(calls) == 2, "an open breaker must not call the dependency"


def test_success_resets_the_count(m):
    cb = m.CircuitBreaker(2, 10, Clock())
    with pytest.raises(RuntimeError):
        cb.call(boom)
    cb.call(lambda: "ok")
    with pytest.raises(RuntimeError):
        cb.call(boom)
    assert cb.state == "closed", "failures must be consecutive"


def test_half_open_success_closes(m):
    clock = Clock()
    cb = m.CircuitBreaker(1, 10, clock)
    with pytest.raises(RuntimeError):
        cb.call(boom)
    clock.t = 10
    assert cb.state == "half_open"
    assert cb.call(lambda: "probe ok") == "probe ok" and cb.state == "closed"


def test_half_open_failure_reopens_immediately_and_restarts_timer(m):
    clock = Clock()
    cb = m.CircuitBreaker(3, 10, clock)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(boom)
    clock.t = 10
    with pytest.raises(RuntimeError):
        cb.call(boom)  # the single probe fails
    assert cb.state == "open"
    clock.t = 15
    assert cb.state == "open", "the reset timer restarts from the failed probe"
    clock.t = 20
    assert cb.state == "half_open"
