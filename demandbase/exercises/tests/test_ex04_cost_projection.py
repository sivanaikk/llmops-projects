import pytest

TABLE = {"chat-small": (0.10, 0.40), "judge": (0.20, 0.80)}


@pytest.fixture
def m(impl):
    return impl("ex04_cost_projection")


def test_shadow_price(m):
    assert m.shadow_price("chat-small", 1_000_000, 500_000, TABLE) == pytest.approx(0.30)
    assert m.shadow_price("unknown", 10, 10, TABLE) == 0.0


def test_projection(m):
    assert m.project_month_end(10.0, 11, 0, 31) == pytest.approx(31.0)   # 10 days in
    assert m.project_month_end(1.0, 1, 0, 30) == pytest.approx(720.0)    # first hour floor


def sev(alerts):
    return sorted(s for s, _ in alerts)


def test_alerts(m):
    assert m.alert(10, 30, 100) == []
    assert sev(m.alert(55, 90, 100)) == ["info"]
    assert sev(m.alert(55, 140, 100)) == ["info", "warning"]
    assert sev(m.alert(85, 95, 100)) == ["warning"]
    assert sev(m.alert(120, 200, 100)) == ["critical"], "no 'on pace' once already over"
