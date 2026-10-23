import random

import pytest


@pytest.fixture
def m(impl):
    return impl("ex04_psi")


def sample(mu, sigma, n, seed):
    rng = random.Random(seed)
    return [rng.lognormvariate(mu, sigma) for _ in range(n)]


def test_same_distribution_is_stable(m):
    v = m.psi(sample(4.2, 0.4, 3000, 1), sample(4.2, 0.4, 500, 2))
    assert v < 0.1 and m.severity(v) == "ok"


def test_shifted_distribution_is_significant(m):
    v = m.psi(sample(4.2, 0.4, 3000, 1), sample(5.2, 0.4, 500, 2))  # questions ~2.7x longer
    assert v > 0.25 and m.severity(v) == "critical"


def test_moderate_shift(m):
    v = m.psi(sample(4.2, 0.4, 5000, 1), sample(4.4, 0.4, 2000, 2))
    assert 0.1 <= v <= 0.5


def test_empty_bins_do_not_crash(m):
    assert m.psi(list(range(100)), [1000] * 50) > 1


def test_severity_cutoffs(m):
    assert [m.severity(x) for x in (0.05, 0.1, 0.2, 0.26)] == ["ok", "warning", "warning", "critical"]
