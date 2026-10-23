import hashlib

import pytest


def embed(text):
    v = [0.0] * 64
    for w in text.lower().split():
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
    n = sum(x * x for x in v) ** 0.5 or 1
    return [x / n for x in v]


@pytest.fixture
def m(impl):
    return impl("ex02_cache_isolation")


def test_paraphrase_still_hits(m):
    c = m.SemanticCache(embed, threshold=0.8)
    s = c.scope("acme", "chat-small", "v2")
    c.store(s, "what is the intent score for northwind", "87")
    assert c.lookup(s, "what is the intent score for northwind please") == "87"


def test_tenants_never_share_answers(m):
    c = m.SemanticCache(embed, threshold=0.8)
    c.store(c.scope("acme", "chat-small", "v2"), "summarise our pipeline", "ACME CONFIDENTIAL")
    assert c.lookup(c.scope("globex", "chat-small", "v2"), "summarise our pipeline") is None


def test_prompt_version_changes_the_answer(m):
    c = m.SemanticCache(embed, threshold=0.8)
    c.store(c.scope("acme", "chat-small", "v1"), "q", "answer under prompt v1")
    assert c.lookup(c.scope("acme", "chat-small", "v2"), "q") is None


@pytest.mark.parametrize("req,ok", [
    ({"temperature": 0}, True),
    ({}, True),
    ({"temperature": 0.9}, False),
    ({"temperature": 0, "tools": [{"type": "function"}]}, False),
    ({"temperature": 0, "stream": True}, False),
])
def test_cacheable(m, req, ok):
    assert m.SemanticCache.cacheable(req) is ok
