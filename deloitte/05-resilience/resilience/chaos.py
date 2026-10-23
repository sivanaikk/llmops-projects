"""Chaos experiments for the agent's dependencies, driven through Toxiproxy.

Each experiment follows the Principles of Chaos shape:

1. **steady state** - probe the agent; abort if it isn't healthy to begin with
2. **inject**       - add a Toxiproxy toxic (latency, timeout, resets) or cut the link
3. **verify**       - probe again; the hypothesis says what "still OK" means under fault
4. **rollback**     - always, even if a probe crashes
5. **recover**      - the system must return to steady state on its own

    python -m resilience.chaos experiments/llm-latency.yaml
    python -m resilience.chaos experiments/*.yaml --report chaos-report.md

The same experiments map to Azure Chaos Studio / AWS FIS for cloud
environments (see cloud/); Toxiproxy makes them runnable on a laptop.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

QUESTIONS = ["Is payments-api healthy right now?", "Which runbook should I follow for high p95 latency?",
             "Is the release gate for doc-ingest open?"]


@dataclass
class ProbeResult:
    n: int
    success_rate: float
    p95_s: float
    outcomes: dict[str, int]

    def meets(self, expect: dict) -> list[str]:
        bad = []
        if "min_success_rate" in expect and self.success_rate < expect["min_success_rate"]:
            bad.append(f"success rate {self.success_rate:.0%} < {expect['min_success_rate']:.0%}")
        if "max_p95_s" in expect and self.p95_s > expect["max_p95_s"]:
            bad.append(f"p95 {self.p95_s:.1f}s > {expect['max_p95_s']}s")
        allowed = expect.get("allowed_outcomes")
        if allowed:
            unexpected = {k: v for k, v in self.outcomes.items() if k not in allowed}
            if unexpected:
                bad.append(f"unexpected outcomes {unexpected}")
        return bad


@dataclass
class ExperimentResult:
    name: str
    passed: bool
    phases: dict[str, ProbeResult | None] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


class AgentProbe:
    def __init__(self, base_url: str, client: httpx.Client | None = None, clock=time.perf_counter):
        self.base_url = base_url.rstrip("/")
        self.http = client or httpx.Client(timeout=120)
        self.clock = clock

    def run(self, n: int) -> ProbeResult:
        lat, outcomes = [], {}
        for i in range(n):
            t0 = self.clock()
            try:
                r = self.http.post(f"{self.base_url}/run", json={"question": QUESTIONS[i % len(QUESTIONS)]})
                outcome = r.json().get("outcome", "http_error") if r.status_code == 200 else f"http_{r.status_code}"
            except httpx.HTTPError:
                outcome = "http_error"
            lat.append(self.clock() - t0)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        lat.sort()
        p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))] if lat else 0.0
        return ProbeResult(n, outcomes.get("success", 0) / n if n else 0.0, p95, outcomes)


class Toxiproxy:
    def __init__(self, base_url: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.http = client or httpx.Client(timeout=10)

    def add_toxic(self, proxy: str, toxic: dict) -> str:
        body = {"name": toxic.get("name", f"chaos-{toxic['type']}"), "type": toxic["type"],
                "stream": toxic.get("stream", "downstream"), "toxicity": toxic.get("toxicity", 1.0),
                "attributes": toxic.get("attributes", {})}
        self.http.post(f"{self.base_url}/proxies/{proxy}/toxics", json=body).raise_for_status()
        return body["name"]

    def remove_toxic(self, proxy: str, name: str) -> None:
        r = self.http.delete(f"{self.base_url}/proxies/{proxy}/toxics/{name}")
        if r.status_code not in (204, 404):
            r.raise_for_status()

    def set_enabled(self, proxy: str, enabled: bool) -> None:
        self.http.post(f"{self.base_url}/proxies/{proxy}", json={"enabled": enabled}).raise_for_status()


def run_experiment(spec: dict, probe: AgentProbe, toxi: Toxiproxy, sleep=time.sleep) -> ExperimentResult:
    res = ExperimentResult(spec["name"], passed=False)
    n = spec.get("probe_requests", 6)

    before = probe.run(n)
    res.phases["steady_state"] = before
    bad = before.meets(spec["steady_state"])
    if bad:
        res.failures = ["steady state not met before injection, aborted: " + "; ".join(bad)]
        return res

    fault = spec["fault"]
    proxy = fault["proxy"]
    injected: list[str] = []
    try:
        if fault["kind"] == "toxic":
            injected.append(toxi.add_toxic(proxy, fault["toxic"]))
        elif fault["kind"] == "outage":
            toxi.set_enabled(proxy, False)
        else:
            raise ValueError(f"unknown fault kind {fault['kind']}")
        sleep(spec.get("settle_s", 2))
        during = probe.run(n)
        res.phases["during_fault"] = during
        res.failures += [f"during fault: {b}" for b in during.meets(spec["hypothesis"])]
    finally:
        for name in injected:
            toxi.remove_toxic(proxy, name)
        if fault["kind"] == "outage":
            toxi.set_enabled(proxy, True)

    sleep(spec.get("recovery_wait_s", 5))
    after = probe.run(n)
    res.phases["recovery"] = after
    res.failures += [f"after rollback: {b}" for b in after.meets(spec["steady_state"])]
    res.passed = not res.failures
    return res


def render(results: list[ExperimentResult]) -> str:
    lines = ["### Chaos experiments", "", "| experiment | result | steady | during fault | recovery |", "|---|---|---|---|---|"]

    def cell(p):
        return "-" if p is None else f"{p.success_rate:.0%} ok, p95 {p.p95_s:.1f}s {p.outcomes}"

    for r in results:
        lines.append(f"| {r.name} | {'PASS' if r.passed else 'FAIL'} | {cell(r.phases.get('steady_state'))} | "
                     f"{cell(r.phases.get('during_fault'))} | {cell(r.phases.get('recovery'))} |")
    for r in results:
        for f in r.failures:
            lines.append(f"- **{r.name}**: {f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chaos")
    ap.add_argument("experiments", nargs="+", type=Path)
    ap.add_argument("--agent", default="http://localhost:8000")
    ap.add_argument("--toxiproxy", default="http://localhost:8474")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args(argv)

    probe, toxi = AgentProbe(args.agent), Toxiproxy(args.toxiproxy)
    results = []
    for path in args.experiments:
        spec = yaml.safe_load(path.read_text())
        print(f"running {spec['name']}: {spec.get('description', '')}", file=sys.stderr)
        results.append(run_experiment(spec, probe, toxi))
    md = render(results)
    print(md)
    if args.report:
        args.report.write_text(md)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
