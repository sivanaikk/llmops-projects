import pytest


@pytest.fixture
def m(impl):
    return impl("ex05_pass_k")


TRIALS = {
    "status": [True, True, True],
    "budget": [True, False, True],
    "math": [False, False, False],
    "runbook": [True, True, False],
}


def test_pass_at_1(m):
    assert m.pass_at_1(TRIALS) == pytest.approx(7 / 12)


def test_pass_hat_k(m):
    assert m.pass_hat_k(TRIALS) == pytest.approx(1 / 4)


def test_flaky(m):
    assert m.flaky(TRIALS) == ["budget", "runbook"]


def test_pass_at_k_estimate(m):
    assert m.pass_at_k_estimate(10, 0, 3) == 0.0
    assert m.pass_at_k_estimate(10, 10, 3) == 1.0
    assert m.pass_at_k_estimate(10, 5, 1) == pytest.approx(0.5)
    assert m.pass_at_k_estimate(10, 2, 9) == 1.0          # n - c < k
    assert m.pass_at_k_estimate(5, 2, 2) == pytest.approx(1 - 3 / 10)
