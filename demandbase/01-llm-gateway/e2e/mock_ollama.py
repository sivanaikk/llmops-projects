"""A fake Ollama server for gateway CI and game days.

Implements the handful of endpoints LiteLLM calls (/api/chat, /api/embed,
/api/show, /api/tags) with deterministic replies, plus admin endpoints to
inject failure or latency, so failover, retries and alerting can be tested in
seconds without downloading a model.

    uvicorn mock_ollama:app --port 11434
    curl -XPOST localhost:11434/admin/fail?rate=1.0     # simulate an outage
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import time

from fastapi import FastAPI, HTTPException, Request

app = FastAPI()
STATE = {"fail_rate": 0.0, "latency_s": 0.0, "calls": 0, "name": os.getenv("MOCK_NAME", "mock")}


@app.post("/admin/fail")
def admin_fail(rate: float = 1.0):
    STATE["fail_rate"] = rate
    return STATE


@app.post("/admin/latency")
def admin_latency(seconds: float = 0.0):
    STATE["latency_s"] = seconds
    return STATE


@app.get("/admin/state")
def admin_state():
    return STATE


async def _maybe_fail():
    STATE["calls"] += 1
    if STATE["latency_s"]:
        await asyncio.sleep(STATE["latency_s"])
    if random.random() < STATE["fail_rate"]:
        raise HTTPException(status_code=503, detail=f"{STATE['name']} unavailable (injected)")


def _tokens(text: str) -> int:
    return max(1, len(text.split()))


@app.get("/api/tags")
def tags():
    return {"models": [{"name": m} for m in ("qwen2.5:0.5b", "smollm2:360m", "qwen2.5:1.5b", "all-minilm")]}


@app.post("/api/show")
async def show(req: Request):
    return {"model_info": {"general.context_length": 32768}, "template": "", "details": {"family": "qwen2"}}


@app.post("/api/chat")
async def chat(req: Request):
    await _maybe_fail()
    body = await req.json()
    messages = body.get("messages", [])
    last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    reply = f"[{STATE['name']}:{body.get('model')}] You asked: {last[:200]}"
    prompt = " ".join(str(m.get("content", "")) for m in messages)
    return {
        "model": body.get("model"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": {"role": "assistant", "content": reply},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": _tokens(prompt),
        "eval_count": _tokens(reply),
    }


def _vec(text: str, dim: int = 384) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    rnd = random.Random(h)
    return [rnd.uniform(-1, 1) for _ in range(dim)]


@app.post("/api/embed")
async def embed(req: Request):
    await _maybe_fail()
    body = await req.json()
    inputs = body.get("input")
    inputs = [inputs] if isinstance(inputs, str) else inputs
    return {"model": body.get("model"), "embeddings": [_vec(t) for t in inputs],
            "prompt_eval_count": sum(_tokens(t) for t in inputs)}


@app.post("/api/embeddings")
async def embeddings_legacy(req: Request):
    await _maybe_fail()
    body = await req.json()
    return {"embedding": _vec(body.get("prompt", ""))}
