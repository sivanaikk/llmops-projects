"""Game-day scenarios against the local docker-compose stack.

    python 09-sre/tools/game_day.py --scenario primary-outage --minutes 5
    python 09-sre/tools/game_day.py --scenario slow-provider

Each scenario: inject the fault, keep a steady probe running, print what users
saw (errors, latency, which backend served them), then restore. Watch Grafana
(localhost:3000) and Prometheus alerts (localhost:9090/alerts) while it runs.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections import Counter

import httpx

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:4000")
KEY = os.getenv("GATEWAY_API_KEY", os.getenv("LITELLM_MASTER_KEY", "sk-local-master"))
COMPOSE = ["docker", "compose"]


def compose(*args: str) -> None:
    print("$", " ".join(COMPOSE + list(args)))
    subprocess.run(COMPOSE + list(args), check=True)


def probe(client: httpx.Client, i: int) -> tuple[str, float, str]:
    t0 = time.perf_counter()
    try:
        r = client.post("/v1/chat/completions", json={
            "model": "chat-small", "max_tokens": 16, "metadata": {"feature": "gameday"},
            "messages": [{"role": "user", "content": f"game day probe {i}: say ok"}]})
        served = r.headers.get("x-litellm-model-id", "?")
        return str(r.status_code), time.perf_counter() - t0, served
    except httpx.HTTPError as e:
        return type(e).__name__, time.perf_counter() - t0, "-"


def embed_probe(client: httpx.Client) -> str:
    try:
        return str(client.post("/v1/embeddings", json={"model": "embed-small", "input": "probe"}).status_code)
    except httpx.HTTPError as e:
        return type(e).__name__


SCENARIOS = {
    # name: (inject, restore)
    "primary-outage": (lambda: compose("stop", "ollama-primary"), lambda: compose("start", "ollama-primary")),
    "secondary-outage": (lambda: compose("stop", "ollama-secondary"), lambda: compose("start", "ollama-secondary")),
    # 2s of added latency on the primary's network interface (needs NET_ADMIN in the container image).
    "slow-provider": (
        lambda: compose("exec", "-u", "root", "ollama-primary", "sh", "-c", "tc qdisc add dev eth0 root netem delay 2000ms"),
        lambda: compose("exec", "-u", "root", "ollama-primary", "sh", "-c", "tc qdisc del dev eth0 root"),
    ),
    "redis-outage": (lambda: compose("stop", "redis"), lambda: compose("start", "redis")),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    inject, restore = SCENARIOS[args.scenario]
    client = httpx.Client(base_url=GATEWAY, headers={"Authorization": f"Bearer {KEY}"}, timeout=90)

    print(f"baseline: {probe(client, 0)}  embeddings={embed_probe(client)}")
    inject()
    codes, served, lat, emb = Counter(), Counter(), [], Counter()
    deadline = time.time() + args.minutes * 60
    i = 0
    try:
        while time.time() < deadline:
            i += 1
            code, latency, s = probe(client, i)
            codes[code] += 1
            served[s] += 1
            lat.append(latency)
            if i % 5 == 0:
                emb[embed_probe(client)] += 1
                print(f"t+{i * args.interval:>5.0f}s  chat codes={dict(codes)} served_by={dict(served)} embeddings={dict(emb)}")
            time.sleep(args.interval)
    finally:
        restore()

    lat.sort()
    err = 1 - codes.get("200", 0) / max(sum(codes.values()), 1)
    print(f"\n== {args.scenario} summary ==")
    print(f"chat error rate during fault: {err:.1%}  p95 latency: {lat[int(0.95 * (len(lat) - 1))]:.2f}s")
    print(f"served by: {dict(served)}")
    print(f"embeddings: {dict(emb)}")
    print("Now: check which alerts fired (localhost:9090/alerts) and fill in the game-day write-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
