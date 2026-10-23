import pytest


@pytest.fixture
def m(impl):
    return impl("ex05_bootstrap_gate")


def test_identical_is_zero_width(m):
    assert m.bootstrap_ci([0.0] * 20) == (0.0, 0.0)


def test_ci_contains_the_mean(m):
    diffs = [0.0, 0.1, -0.1, 0.05, 0.0] * 10
    lo, hi = m.bootstrap_ci(diffs)
    assert lo <= 0.01 <= hi and lo < hi


def test_noise_is_not_a_regression(m):
    # 16 examples, two lost and one gained a point: mean -0.06 but very uncertain
    diffs = [0.0] * 13 + [-1.0, -1.0, 1.0]
    assert not m.is_regression(diffs, tolerance=0.05)


def test_consistent_drop_is_a_regression(m):
    diffs = [-1.0] * 6 + [0.0] * 10
    assert m.is_regression(diffs, tolerance=0.05)
