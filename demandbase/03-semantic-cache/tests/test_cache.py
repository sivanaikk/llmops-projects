from semcache import HashingEmbedder, SemanticCache


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make(threshold=0.6, **kw):
    return SemanticCache(HashingEmbedder(), threshold=threshold, **kw)


def test_exact_hit_ignores_case_and_whitespace():
    c = make()
    s = c.scope("team-a", "chat-small")
    c.store(s, "What is the intent score for Acme?", "42")
    res = c.lookup(s, "  what is the INTENT score for acme? ")
    assert res.hit and res.kind == "exact" and res.response == "42"


def test_semantic_hit_on_paraphrase():
    c = make(threshold=0.5)
    s = c.scope("team-a", "chat-small")
    c.store(s, "Summarize recent engagement for Acme Logistics", "summary")
    res = c.lookup(s, "Give me a summary of recent engagement for Acme Logistics")
    assert res.hit and res.kind == "semantic"


def test_miss_below_threshold():
    c = make(threshold=0.99)
    s = c.scope("team-a", "chat-small")
    c.store(s, "Who is the economic buyer at Contoso?", "Jane")
    assert not c.lookup(s, "What is the weather in Hyderabad?").hit


def test_tenants_are_isolated():
    c = make()
    c.store(c.scope("team-a", "m"), "q", "secret answer")
    assert not c.lookup(c.scope("team-b", "m"), "q").hit
    assert not c.lookup(c.scope("team-a", "other-model"), "q").hit
    assert not c.lookup(c.scope("team-a", "m", system_prompt="different"), "q").hit


def test_ttl_expiry():
    clock = FakeClock()
    c = make(ttl_seconds=10, clock=clock)
    s = c.scope("t", "m")
    c.store(s, "q", "a")
    clock.t = 11
    assert not c.lookup(s, "q").hit


def test_lru_bound():
    c = make(max_entries_per_scope=2, threshold=1.01)
    s = c.scope("t", "m")
    for q in ["one", "two", "three"]:
        c.store(s, q, q)
    assert not c.lookup(s, "one").hit
    assert c.lookup(s, "three").hit


def test_cacheable_rules():
    assert SemanticCache.cacheable({"temperature": 0})
    assert not SemanticCache.cacheable({"temperature": 0.9})
    assert not SemanticCache.cacheable({"tools": [{"type": "function"}]})
    assert not SemanticCache.cacheable({"stream": True})


def test_get_or_call_only_calls_on_miss():
    c = make()
    s = c.scope("t", "m")
    calls = []
    fn = lambda p: calls.append(p) or "resp"  # noqa: E731
    c.get_or_call(s, "hello world", fn)
    c.get_or_call(s, "hello world", fn)
    assert len(calls) == 1
    assert c.stats.hit_rate == 0.5
