"""Capacity planning from a load-test result.

Agent requests are long-lived (seconds to tens of seconds), so capacity is
about **concurrency**, not request rate. Little's law: L = lambda x W, i.e.
in-flight requests = arrival rate x time in system.

    python -m resilience.capacity --k6-summary summary.json --target-rps 5
    python -m resilience.capacity --observed-rps 1 --avg-latency 8 --target-rps 5 --tokens-per-run 3000
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Plan:
    target_rps: float
    avg_latency_s: float
    p95_latency_s: float
    in_flight_avg: float
    in_flight_p95: float
    pod_replicas: int
    hpa_min: int
    hpa_max: int
    model_tokens_per_s: float
    notes: list[str]


def plan(target_rps: float, avg_latency_s: float, p95_latency_s: float, per_pod_concurrency: int = 8,
         headroom: float = 0.3, tokens_per_run: float = 3000, zones: int = 3, spike_factor: float = 5.0) -> Plan:
    notes = []
    in_flight = target_rps * avg_latency_s
    # Size for p95 latency so a slow tail doesn't exhaust worker slots.
    in_flight_p95 = target_rps * p95_latency_s
    replicas = max(zones, math.ceil(in_flight_p95 * (1 + headroom) / per_pod_concurrency))
    hpa_max = max(replicas, math.ceil(target_rps * spike_factor * p95_latency_s / per_pod_concurrency))
    tokens_s = target_rps * tokens_per_run
    if replicas == zones:
        notes.append(f"replica count set by zone spread ({zones}), not load")
    if p95_latency_s > 3 * avg_latency_s:
        notes.append("p95 > 3x average: long tail. Check the step distribution before adding pods")
    notes.append(f"model backend must sustain ~{tokens_s:,.0f} tokens/s; CPU-hosted small models do roughly "
                 "50-300 tokens/s per node, so scale the model tier, not just the agent pods")
    return Plan(target_rps, avg_latency_s, p95_latency_s, round(in_flight, 2), round(in_flight_p95, 2),
                replicas, replicas, hpa_max, round(tokens_s, 1), notes)


def from_k6_summary(path: str | Path) -> tuple[float, float, float]:
    """(observed rps, avg latency s, p95 latency s) from `k6 run --summary-export`."""
    m = json.loads(Path(path).read_text())["metrics"]
    d = m.get("http_req_duration{endpoint:run}") or m["http_req_duration"]
    return m["http_reqs"]["rate"], d["avg"] / 1000, d["p(95)"] / 1000


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="capacity")
    ap.add_argument("--k6-summary")
    ap.add_argument("--observed-rps", type=float)
    ap.add_argument("--avg-latency", type=float)
    ap.add_argument("--p95-latency", type=float)
    ap.add_argument("--target-rps", type=float, required=True)
    ap.add_argument("--per-pod-concurrency", type=int, default=8)
    ap.add_argument("--tokens-per-run", type=float, default=3000)
    args = ap.parse_args(argv)
    if args.k6_summary:
        _, avg, p95 = from_k6_summary(args.k6_summary)
    elif args.avg_latency:
        avg, p95 = args.avg_latency, args.p95_latency or args.avg_latency * 2
    else:
        ap.error("give --k6-summary or --avg-latency")
    print(json.dumps(asdict(plan(args.target_rps, avg, p95, args.per_pod_concurrency, tokens_per_run=args.tokens_per_run)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
