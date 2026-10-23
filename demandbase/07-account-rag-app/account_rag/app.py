"""Account Intel: a RAG feature built the way a product team would build on the runtime.

It uses only platform pieces: the gateway (models, keys, guardrails, cost),
semcache (tenant-scoped semantic cache) and llmobs (traces). The evals harness
treats `AccountAssistant.answer` as the system under test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .gateway import ChatClient
from .index import VectorIndex, load_chunks
from .prompts import PROMPTS

FEATURE = "account-summary"
TEAM = "account-intel"


@dataclass
class AssistantConfig:
    model: str = "chat-small"
    embed_model: str = "embed-small"
    prompt_version: str = "v2"
    top_k: int = 3
    temperature: float = 0.0
    max_tokens: int = 200
    use_cache: bool = True


@dataclass
class Answer:
    text: str
    contexts: list[str]
    sources: list[str]
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0
    cache: str = "miss"
    model: str = ""


class AccountAssistant:
    def __init__(self, client: ChatClient, config: AssistantConfig | None = None, embed=None, cache=None, tracer=None):
        self.client = client
        self.cfg = config or AssistantConfig()
        self.embed = embed or (lambda t: client.embed(self.cfg.embed_model, t, feature=FEATURE))
        self.index = VectorIndex(self.embed).add(load_chunks())
        self.cache = cache
        if tracer is None:
            from llmobs import LLMTracer

            tracer = LLMTracer()
        self.tracer = tracer

    def answer(self, question: str) -> Answer:
        t0 = time.perf_counter()
        with self.tracer.step("account_intel.answer", **{"app.prompt_version": self.cfg.prompt_version}):
            with self.tracer.step("retrieve", **{"retrieval.top_k": self.cfg.top_k}) as span:
                hits = self.index.search(question, k=self.cfg.top_k)
                span.set_attribute("retrieval.sources", [c.id for c, _ in hits])
            contexts = [c.text for c, _ in hits]
            sources = [c.id for c, _ in hits]
            system = PROMPTS[self.cfg.prompt_version].format(
                context="\n\n".join(f"[{c.id}]\n{c.text}" for c, _ in hits)
            )

            scope = None
            if self.cache is not None and self.cfg.use_cache:
                scope = self.cache.scope(TEAM, self.cfg.model, system)
                res = self.cache.lookup(scope, question)
                if res.hit:
                    return Answer(res.response, contexts, sources, {}, time.perf_counter() - t0, res.kind, self.cfg.model)

            messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
            with self.tracer.llm_call("chat", self.cfg.model, feature=FEATURE, team=TEAM) as s:
                s.record_prompt(messages)
                resp = self.client.chat(self.cfg.model, messages, feature=FEATURE,
                                        temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens)
                s.record_response(resp)
            text = (resp["choices"][0]["message"]["content"] or "").strip()
            if scope is not None:
                self.cache.store(scope, question, text)
            return Answer(text, contexts, sources, resp.get("usage") or {}, time.perf_counter() - t0, "miss",
                          resp.get("model", self.cfg.model))
