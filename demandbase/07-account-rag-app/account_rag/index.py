"""Tiny in-memory vector index over the account notes.

Small corpus, so brute-force cosine is exact and fast. Each chunk is one
`## section` of an account file, prefixed with the account name so a question
about "Northwind's buyer" doesn't retrieve Acme's buying group.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "accounts"


@dataclass
class Chunk:
    id: str
    account: str
    section: str
    text: str


def load_chunks(data_dir: Path = DATA_DIR) -> list[Chunk]:
    chunks = []
    for path in sorted(data_dir.glob("*.md")):
        raw = path.read_text()
        account = re.search(r"^# (.+)$", raw, re.M).group(1).strip()
        for sec in re.split(r"^## ", raw, flags=re.M)[1:]:
            title, _, body = sec.partition("\n")
            chunks.append(Chunk(f"{path.stem}#{title.strip().lower().replace(' ', '-')}", account, title.strip(),
                                f"{account} - {title.strip()}\n{body.strip()}"))
    return chunks


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class VectorIndex:
    def __init__(self, embed: Callable[[str], list[float]]):
        self.embed = embed
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def add(self, chunks: list[Chunk]) -> VectorIndex:
        for c in chunks:
            self.chunks.append(c)
            self.vectors.append(_norm(self.embed(c.text)))
        return self

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = _norm(self.embed(query))
        scored = []
        ql = query.lower()
        for c, v in zip(self.chunks, self.vectors):
            s = sum(a * b for a, b in zip(q, v))
            # Entity boost: small embedding models are weak at proper nouns.
            if c.account.lower().split()[0] in ql:
                s += 0.25
            scored.append((c, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
