"""Shadow pricing for self-hosted models.

Local Ollama models report $0, which makes showback useless: teams can't see
what their usage *would* cost on a hosted provider, and the platform can't
show savings from caching or model downsizing. We price each model group at a
reference rate (USD per 1M tokens). The numbers are illustrative; keep them in
sync with `01-llm-gateway/config.yaml` `model_info` so the gateway's own
`response_cost` and this table agree.
"""

from __future__ import annotations

PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    # model group      (input, output)
    "chat-small": (0.10, 0.40),
    "chat-tiny": (0.05, 0.20),
    "judge": (0.20, 0.80),
    "embed-small": (0.02, 0.0),
}


def price(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = PRICE_PER_MTOK.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000
