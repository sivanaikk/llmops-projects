"""Two-tier response cache: exact match first, then semantic similarity.

Design points that matter in production:

* **Scope keys.** Entries are partitioned by (tenant, model, system prompt
  hash). A semantic hit must never leak one tenant's answer to another, and an
  answer produced under a different system prompt is not the same answer.
* **Only cache deterministic-ish calls.** Requests with temperature > 0 or
  tool calls are skipped by default; caching them silently changes behaviour.
* **Threshold is a product decision.** Too low and users get confidently wrong
  answers to a different question. `bench/benchmark.py` measures the hit-rate
  vs false-hit trade-off so the threshold is chosen from data.
* **TTL + bounded size.** Cached answers about accounts go stale.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from .embedders import Embedder, Vector, cosine


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def normalize_prompt(text: str) -> str:
    return " ".join(text.lower().split())


@dataclass
class CacheEntry:
    prompt: str
    response: str
    vector: Vector
    created_at: float
    hits: int = 0


@dataclass
class CacheResult:
    hit: bool
    kind: str | None = None  # "exact" | "semantic"
    response: str | None = None
    similarity: float | None = None
    matched_prompt: str | None = None


@dataclass
class CacheStats:
    lookups: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    skipped: int = 0
    by_scope: dict[str, int] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        return (self.exact_hits + self.semantic_hits) / self.lookups if self.lookups else 0.0


class SemanticCache:
    def __init__(
        self,
        embedder: Embedder,
        threshold: float = 0.90,
        ttl_seconds: float = 3600,
        max_entries_per_scope: int = 5000,
        clock=time.monotonic,
    ):
        self.embedder = embedder
        self.threshold = threshold
        self.ttl = ttl_seconds
        self.max_entries = max_entries_per_scope
        self.clock = clock
        self._exact: dict[str, OrderedDict[str, CacheEntry]] = {}
        self.stats = CacheStats()

    @staticmethod
    def scope(tenant: str, model: str, system_prompt: str = "") -> str:
        return _hash(tenant, model, system_prompt)[:16]

    @staticmethod
    def cacheable(request: dict) -> bool:
        if request.get("temperature", 0) and request["temperature"] > 0.2:
            return False
        if request.get("tools") or request.get("stream"):
            return False
        return not request.get("cache", {}).get("no-cache", False)

    def _bucket(self, scope: str) -> OrderedDict[str, CacheEntry]:
        return self._exact.setdefault(scope, OrderedDict())

    def _expired(self, e: CacheEntry) -> bool:
        return self.clock() - e.created_at > self.ttl

    def lookup(self, scope: str, prompt: str) -> CacheResult:
        self.stats.lookups += 1
        bucket = self._bucket(scope)
        key = _hash(normalize_prompt(prompt))

        entry = bucket.get(key)
        if entry and not self._expired(entry):
            entry.hits += 1
            bucket.move_to_end(key)
            self.stats.exact_hits += 1
            return CacheResult(True, "exact", entry.response, 1.0, entry.prompt)

        q = self.embedder.embed(prompt)
        best, best_sim = None, -1.0
        # Linear scan is fine for thousands of entries per scope; swap for an
        # ANN index (Redis/Qdrant HNSW) when a scope grows past that.
        for k, e in list(bucket.items()):
            if self._expired(e):
                del bucket[k]
                continue
            sim = cosine(q, e.vector)
            if sim > best_sim:
                best, best_sim = e, sim
        if best and best_sim >= self.threshold:
            best.hits += 1
            self.stats.semantic_hits += 1
            return CacheResult(True, "semantic", best.response, round(best_sim, 4), best.prompt)
        return CacheResult(False, similarity=round(best_sim, 4) if best else None)

    def store(self, scope: str, prompt: str, response: str) -> None:
        bucket = self._bucket(scope)
        key = _hash(normalize_prompt(prompt))
        bucket[key] = CacheEntry(prompt, response, self.embedder.embed(prompt), self.clock())
        bucket.move_to_end(key)
        while len(bucket) > self.max_entries:
            bucket.popitem(last=False)
        self.stats.by_scope[scope] = len(bucket)

    def get_or_call(self, scope: str, prompt: str, call) -> tuple[str, CacheResult]:
        res = self.lookup(scope, prompt)
        if res.hit:
            return res.response, res
        response = call(prompt)
        self.store(scope, prompt, response)
        return response, res

    def snapshot(self) -> str:
        s = self.stats
        return json.dumps(
            {"lookups": s.lookups, "exact_hits": s.exact_hits, "semantic_hits": s.semantic_hits, "hit_rate": round(s.hit_rate, 3)}
        )
