"""Reference solution for exercise 02."""

import hashlib


def _h(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(self, embed, threshold: float = 0.9):
        self.embed, self.threshold = embed, threshold
        self.store_: dict[str, list[tuple[list[float], str]]] = {}

    @staticmethod
    def scope(tenant: str, model: str, system_prompt: str) -> str:
        return _h(tenant, model, system_prompt)

    @staticmethod
    def cacheable(request: dict) -> bool:
        if (request.get("temperature") or 0) > 0.2:
            return False  # sampled answers vary on purpose; caching freezes one sample
        return not request.get("tools") and not request.get("stream")

    def lookup(self, scope: str, prompt: str):
        q = self.embed(prompt)
        best = max(self.store_.get(scope, []), key=lambda e: sum(a * b for a, b in zip(q, e[0])), default=None)
        if best and sum(a * b for a, b in zip(q, best[0])) >= self.threshold:
            return best[1]
        return None

    def store(self, scope: str, prompt: str, response: str) -> None:
        self.store_.setdefault(scope, []).append((self.embed(prompt), response))
