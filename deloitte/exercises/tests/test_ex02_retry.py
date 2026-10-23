import random

import pytest


class Transient(Exception):
    pass


class Permanent(Exception):
    pass


@pytest.fixture
def m(impl):
    return impl("ex02_retry")


def run(m, fn, attempts=4, remaining=lambda: 100.0, sleeps=None, seed=0):
    sleeps = [] if sleeps is None else sleeps
    return m.retry_call(fn, lambda e: isinstance(e, Transient), attempts, 0.5, 4.0, remaining, sleeps.append,
                        random.Random(seed))


def test_succeeds_after_transient_failures(m):
    calls = iter([Transient(), Transient(), "ok"])

    def fn():
        x = next(calls)
        if isinstance(x, Exception):
            raise x
        return x

    sleeps = []
    assert run(m, fn, sleeps=sleeps) == "ok" and len(sleeps) == 2


def test_does_not_retry_permanent_errors(m):
    calls = []

    def fn():
        calls.append(1)
        raise Permanent()

    with pytest.raises(Permanent):
        run(m, fn)
    assert len(calls) == 1


def test_reraises_after_last_attempt(m):
    calls = []

    def fn():
        calls.append(1)
        raise Transient()

    with pytest.raises(Transient):
        run(m, fn, attempts=3)
    assert len(calls) == 3


def test_full_jitter_bounds(m):
    sleeps = []

    def fn():
        raise Transient()

    for seed in range(50):
        with pytest.raises(Transient):
            run(m, fn, attempts=5, sleeps=sleeps, seed=seed)
    # 4 sleeps per run; attempt n is capped at min(4, 0.5 * 2**(n-1)) = 0.5, 1, 2, 4
    caps = [0.5, 1, 2, 4] * 50
    assert all(0 <= s <= c for s, c in zip(sleeps, caps))
    assert len(set(round(s, 6) for s in sleeps)) > 100, "sleeps must be random (jitter), not fixed"


def test_respects_deadline(m):
    t = {"left": 1.0}
    sleeps = []

    def fn():
        t["left"] -= 0.7
        raise Transient()

    with pytest.raises((m.DeadlineExceeded, Transient)):
        run(m, fn, attempts=10, remaining=lambda: t["left"], sleeps=sleeps)
    assert all(s <= 1.0 for s in sleeps)
    assert len(sleeps) <= 2, "must stop once the deadline is spent"
