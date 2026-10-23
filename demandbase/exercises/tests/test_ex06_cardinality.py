import pytest


@pytest.fixture
def m(impl):
    return impl("ex06_cardinality")


def guard(m):
    return m.CardinalityGuard({"team": {"account-intel", "internal-tools"}, "model": {"chat-small", "chat-tiny"}})


def test_label(m):
    g = guard(m)
    assert g.label("team", "account-intel") == "account-intel"
    assert g.label("team", "team-of-the-week") == "other"
    assert g.label("model", None) == "other"
    with pytest.raises(KeyError):
        g.label("user_id", "u-123")


def test_series_stay_bounded(m):
    events = [{"team": f"t{i}", "model": f"m{i % 50}", "user_id": f"u{i}"} for i in range(10_000)]
    events += [{"team": "account-intel", "model": "chat-small"}] * 5
    # unguarded this would be 10,000 series; guarded it's {other x other, account-intel x chat-small}
    assert m.series_count(events, guard(m), ["team", "model"]) == 2
