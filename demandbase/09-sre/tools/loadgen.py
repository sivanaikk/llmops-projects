"""Async load generator for the gateway (or the account-intel app).

    python 09-sre/tools/loadgen.py --rps 5 --duration 60
    python 09-sre/tools/loadgen.py --target app --rps 2      # through account-intel /ask

Reports throughput, error rate by status code and latency percentiles, which
is what you need to size quotas and check the latency SLO before a launch.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import time
from collections import Counter

import httpx

QUESTIONS = [
    "What is the intent score for Northwind Robotics?",
    "Who is the economic buyer at Initech SaaS?",
    "Summarize Acme Logistics' engagement this month.",
    "Which CRM does Contoso Health use?",
    "Should we run outbound to Globex Fintech?",
    "Where does Umbrella Analytics want data delivered?",
]


async def one(client: httpx.AsyncClient, target: str, model: str) -> tuple[int, float]:
    q = random.choice(QUESTIONS)
    t0 = time.perf_counter()
    try:
        if target == "app":
            r = await client.post("/ask", json={"question": q})
        else:
            r = await client.post("/v1/chat/completions", json={
                "model": model, "max_tokens": 64,
                # A nonce defeats the exact cache so we measure the model path.
                "messages": [{"role": "user", "content": f"{q} (req {random.random():.6f})"}],
                "metadata": {"feature": "loadtest"}})
        return r.status_code, time.perf_counter() - t0
    except httpx.HTTPError:
        return 599, time.perf_counter() - t0


async def run(args) -> None:
    base = args.url or ("http://localhost:8080" if args.target == "app" else os.getenv("GATEWAY_URL", "http://localhost:4000"))
    headers = {"Authorization": f"Bearer {args.key}"} if args.target == "gateway" else {}
    results: list[tuple[int, float]] = []
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=120) as client:
        tasks = []
        start = time.perf_counter()
        n = int(args.rps * args.duration)
        for _ in range(n):
            # Open-loop arrivals (Poisson): the load doesn't back off when the
            # system slows down, which is how real traffic behaves.
            await asyncio.sleep(random.expovariate(args.rps))
            tasks.append(asyncio.create_task(one(client, args.target, args.model)))
        for t in asyncio.as_completed(tasks):
            results.append(await t)
        elapsed = time.perf_counter() - start

    codes = Counter(c for c, _ in results)
    ok = sorted(lat for code, lat in results if code == 200)
    pct = lambda p: ok[min(len(ok) - 1, int(p * (len(ok) - 1)))] if ok else float("nan")  # noqa: E731
    print(f"requests={len(results)} elapsed={elapsed:.1f}s achieved_rps={len(results) / elapsed:.2f}")
    print(f"status codes: {dict(codes)}  error_rate={1 - codes.get(200, 0) / max(len(results), 1):.1%}")
    if ok:
        print(f"latency p50={pct(.5):.2f}s p95={pct(.95):.2f}s p99={pct(.99):.2f}s mean={statistics.fmean(ok):.2f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["gateway", "app"], default="gateway")
    ap.add_argument("--url")
    ap.add_argument("--key", default=os.getenv("GATEWAY_API_KEY", os.getenv("LITELLM_MASTER_KEY", "sk-local-master")))
    ap.add_argument("--model", default="chat-small")
    ap.add_argument("--rps", type=float, default=2.0)
    ap.add_argument("--duration", type=float, default=30.0)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
