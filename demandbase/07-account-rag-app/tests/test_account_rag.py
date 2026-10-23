import random

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from account_rag import AccountAssistant, AssistantConfig
from account_rag.index import load_chunks
from llmobs import LLMTracer
from semcache import HashingEmbedder, SemanticCache


class FakeGateway:
    """Echoes the first context line so tests can see what was retrieved."""

    def __init__(self):
        self.calls = []

    def chat(self, model, messages, feature, **params):
        self.calls.append(messages)
        first_source = messages[0]["content"].split("[", 2)[2].split("]")[0] if "[" in messages[0]["content"] else ""
        return {"model": model, "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "choices": [{"finish_reason": "stop", "message": {"content": f"answer from {first_source}"}}]}

    def embed(self, model, text, feature):
        raise AssertionError("tests use the hashing embedder")


def assistant(**kw):
    exp = InMemorySpanExporter()
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(exp))
    emb = HashingEmbedder()
    a = AccountAssistant(FakeGateway(), AssistantConfig(**kw), embed=emb.embed,
                         cache=SemanticCache(emb, threshold=0.95),
                         tracer=LLMTracer(tp.get_tracer("t"), capture_ratio=1.0, rng=random.Random(0)))
    return a, exp


def test_corpus_chunks_are_prefixed_with_account():
    chunks = load_chunks()
    assert len(chunks) >= 20
    assert all(c.text.startswith(c.account) for c in chunks)


def test_retrieval_finds_the_right_account():
    a, _ = assistant()
    hits = a.index.search("Who is the economic buyer at Northwind Robotics?", k=3)
    assert hits[0][0].id.startswith("northwind-robotics")


def test_answer_uses_gateway_and_cache():
    a, exp = assistant()
    q = "What is the intent score for Initech SaaS?"
    first = a.answer(q)
    second = a.answer(q)
    assert first.cache == "miss" and second.cache == "exact"
    assert len(a.client.calls) == 1
    assert first.sources[0].startswith("initech-saas")
    names = {s.name for s in exp.get_finished_spans()}
    assert {"account_intel.answer", "retrieve", "chat chat-small"} <= names


def test_prompt_version_changes_system_prompt():
    a, _ = assistant(prompt_version="v1", use_cache=False)
    a.answer("Where is Acme Logistics headquartered?")
    assert a.client.calls[0][0]["content"].startswith("You are an assistant for B2B sales teams")
