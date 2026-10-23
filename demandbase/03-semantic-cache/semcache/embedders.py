"""Embedding backends.

`GatewayEmbedder` goes through the LiteLLM gateway (so embedding spend is
attributed like any other call). `HashingEmbedder` is a dependency-free
bag-of-words embedder used in tests and as a zero-cost fallback.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol

import httpx

Vector = list[float]


class Embedder(Protocol):
    def embed(self, text: str) -> Vector: ...


def normalize(v: Vector) -> Vector:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a: Vector, b: Vector) -> float:
    # Inputs are unit-normalized, so the dot product is the cosine.
    return sum(x * y for x, y in zip(a, b))


class HashingEmbedder:
    """Feature-hashed unigrams+bigrams. Deterministic, fast, no model needed."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, text: str) -> Vector:
        toks = re.findall(r"[a-z0-9]+", text.lower())
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        v = [0.0] * self.dim
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
        return normalize(v)


class GatewayEmbedder:
    """Calls `/v1/embeddings` on the LiteLLM gateway (all-minilm by default)."""

    def __init__(self, model: str = "embed-small", base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self.base_url = (base_url or os.getenv("GATEWAY_URL", "http://localhost:4000")).rstrip("/")
        self.api_key = api_key or os.getenv("GATEWAY_API_KEY", "sk-local-master")
        self._client = httpx.Client(timeout=30)

    def embed(self, text: str) -> Vector:
        r = self._client.post(
            f"{self.base_url}/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": text},
        )
        r.raise_for_status()
        return normalize(r.json()["data"][0]["embedding"])
