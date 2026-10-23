import math

import pytest


@pytest.fixture
def m(impl):
    return impl("ex03_burn_rate")


def test_budget_and_burn(m):
    assert m.error_budget(0.995) == pytest.approx(0.005)
    assert m.burn_rate(0.005, 0.995) == pytest.approx(1.0)
    assert m.burn_rate(0.072, 0.995) == pytest.approx(14.4)


def test_why_14_4(m):
    # 14.4x for one hour spends 2% of a 28-day budget... close to the SRE-workbook number
    # (exactly 2% for a 30-day window: 14.4 * 1 / 720).
    assert m.budget_spent(14.4, 1, window_days=30) == pytest.approx(0.02)
    assert m.budget_spent(1, 28 * 24) == pytest.approx(1.0)


def test_page_needs_both_windows(m):
    assert m.should_page(0.10, 0.10, 0.995)
    assert not m.should_page(0.10, 0.001, 0.995), "already recovered: the 5m window is clean"
    assert not m.should_page(0.001, 0.5, 0.995), "a 5-minute blip alone is not worth waking someone"


def test_hours_to_exhaustion(m):
    assert m.hours_to_exhaustion(1.0, 1.0) == pytest.approx(672)
    assert m.hours_to_exhaustion(0.5, 14.4) == pytest.approx(23.33, abs=0.01)
    assert math.isinf(m.hours_to_exhaustion(0.5, 0))
