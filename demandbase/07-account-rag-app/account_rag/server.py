"""HTTP front for the assistant (used by docker-compose and the load generator).

    uvicorn account_rag.server:app --port 8080
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llmobs import LLMTracer, setup_tracing
from semcache import GatewayEmbedder, SemanticCache

from .app import AccountAssistant, AssistantConfig
from .gateway import GatewayClient, GatewayError

setup_tracing("account-intel")
client = GatewayClient()
cache = SemanticCache(GatewayEmbedder(api_key=client.api_key), threshold=float(os.getenv("SEMCACHE_THRESHOLD", "0.92")))
assistant = AccountAssistant(
    client,
    AssistantConfig(model=os.getenv("CHAT_MODEL", "chat-small"), prompt_version=os.getenv("PROMPT_VERSION", "v2")),
    cache=cache,
    tracer=LLMTracer(),
)
app = FastAPI(title="Account Intel")


class Question(BaseModel):
    question: str


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/ask")
def ask(q: Question):
    try:
        a = assistant.answer(q.question)
    except GatewayError as e:
        # Surface guardrail blocks / budget exhaustion as-is; they're actionable for the caller.
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return {"answer": a.text, "sources": a.sources, "cache": a.cache, "latency_s": round(a.latency_s, 3), "usage": a.usage}


@app.get("/cache/stats")
def cache_stats():
    return cache.snapshot()
