"""Pick a semantic-cache threshold from data, not vibes.

For each labeled pair (a, b, same_intent) we store `a` and look up `b`, then
sweep the similarity threshold and report:

* hit rate     - share of true paraphrases served from cache (spend saved)
* false hits   - share of *different* questions served a cached answer (wrong
                 answers shown to users; this is the number that gets paged)

Usage:
    python bench/benchmark.py                      # offline hashing embedder
    python bench/benchmark.py --gateway            # all-minilm via LiteLLM
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from semcache.embedders import GatewayEmbedder, HashingEmbedder, cosine  # noqa: E402


def load_pairs(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sweep(pairs: list[dict], embedder, thresholds: list[float]) -> list[dict]:
    sims = [(cosine(embedder.embed(p["a"]), embedder.embed(p["b"])), p["same"]) for p in pairs]
    pos = sum(1 for _, same in sims if same) or 1
    neg = sum(1 for _, same in sims if not same) or 1
    rows = []
    for t in thresholds:
        tp = sum(1 for s, same in sims if same and s >= t)
        fp = sum(1 for s, same in sims if not same and s >= t)
        rows.append({"threshold": t, "hit_rate": tp / pos, "false_hit_rate": fp / neg})
    return rows


def recommend(rows: list[dict], max_false_hit: float) -> dict | None:
    ok = [r for r in rows if r["false_hit_rate"] <= max_false_hit]
    return max(ok, key=lambda r: (r["hit_rate"], -r["threshold"])) if ok else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, default=Path(__file__).with_name("pairs.jsonl"))
    ap.add_argument("--gateway", action="store_true", help="use the gateway embedding model")
    ap.add_argument("--max-false-hit", type=float, default=0.0)
    args = ap.parse_args()

    embedder = GatewayEmbedder() if args.gateway else HashingEmbedder()
    rows = sweep(load_pairs(args.pairs), embedder, [round(0.5 + 0.025 * i, 3) for i in range(20)])

    print(f"{'threshold':>9}  {'hit_rate':>8}  {'false_hit':>9}")
    for r in rows:
        print(f"{r['threshold']:>9.3f}  {r['hit_rate']:>8.2f}  {r['false_hit_rate']:>9.2f}")
    best = recommend(rows, args.max_false_hit)
    print("\nrecommended:", json.dumps(best) if best else "none meets the false-hit budget")


if __name__ == "__main__":
    main()
