import pytest


@pytest.fixture
def m(impl):
    return impl("ex06_capacity")


def test_littles_law(m):
    assert m.in_flight(2, 8) == 16
    assert m.in_flight(0.5, 30) == 15


def test_replicas(m):
    assert m.replicas(2, 16, 8, 0.25, 3) == 5        # ceil(32 * 1.25 / 8)
    assert m.replicas(0.1, 3, 8, 0.3, 3) == 3        # zone floor wins
    assert m.replicas(10, 20, 8, 0.0, 3) == 25       # 200 in flight / 8


def test_model_tier_load(m):
    assert m.tokens_per_second(5, 3000) == 15000
