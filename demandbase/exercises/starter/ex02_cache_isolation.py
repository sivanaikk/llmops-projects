"""Exercise 02: find and fix the tenant leak in this semantic cache.   (concept: 03-semantic-cache/LEARN.md)

This cache WORKS: paraphrases hit and latency drops. It also has two production
bugs that would end up in an incident review. The tests describe the required
behaviour; make them pass by fixing `scope()` and `cacheable()`. Leave the rest alone.

Hint: what else, besides the model, changes what a correct answer is?
"""

import hashlib


def _h(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(self, embed, threshold: float = 0.9):
        self.embed, self.threshold = embed, threshold
        self.store_: dict[str, list[tuple[list[float], str]]] = {}

    @staticmethod
    def scope(tenant: str, model: str, system_prompt: str) -> str:
        return _h(model)  # BUG?

    @staticmethod
    def cacheable(request: dict) -> bool:
        return True  # BUG?

    def lookup(self, scope: str, prompt: str):
        q = self.embed(prompt)
        best = max(self.store_.get(scope, []), key=lambda e: sum(a * b for a, b in zip(q, e[0])), default=None)
        if best and sum(a * b for a, b in zip(q, best[0])) >= self.threshold:
            return best[1]
        return None

    def store(self, scope: str, prompt: str, response: str) -> None:
        self.store_.setdefault(scope, []).append((self.embed(prompt), response))
