import json
from pathlib import Path

import httpx
import pytest
import yaml

from resilience.capacity import from_k6_summary, plan
from resilience.chaos import AgentProbe, Toxiproxy, render, run_experiment

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"


class FakeWorld:
    """Simulates the agent + Toxiproxy: the agent's behaviour depends on the injected fault."""

    def __init__(self, fail_fast=True, recovers=True):
        self.toxics, self.enabled = {}, True
        self.fail_fast, self.recovers = fail_fast, recovers
        self.rolled_back = False
        self.clock = 0.0

    def handler(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.startswith("/proxies/ollama/toxics/") and req.method == "DELETE":
            self.toxics.pop(path.rsplit("/", 1)[1], None)
            self.rolled_back = True
            return httpx.Response(204)
        if path == "/proxies/ollama/toxics":
            body = json.loads(req.content)
            self.toxics[body["name"]] = body
            return httpx.Response(200, json=body)
        if path == "/proxies/ollama":
            self.enabled = json.loads(req.content)["enabled"]
            if self.enabled:
                self.rolled_back = True
            return httpx.Response(200, json={})
        if path == "/run":
            return self.run()
        return httpx.Response(404)

    def run(self):
        if self.rolled_back and not self.recovers:
            self.clock += 1
            return httpx.Response(200, json={"outcome": "llm_unavailable"})
        if not self.enabled:
            self.clock += 1 if self.fail_fast else 90
            return httpx.Response(200, json={"outcome": "llm_unavailable"})
        lat = 3 + (3 if any(t["type"] == "latency" for t in self.toxics.values()) else 0)
        self.clock += lat
        return httpx.Response(200, json={"outcome": "success"})


def wire(world):
    client = httpx.Client(transport=httpx.MockTransport(world.handler), base_url="http://x")
    return AgentProbe("http://x", client, clock=lambda: world.clock), Toxiproxy("http://x", client)


def spec(name):
    return yaml.safe_load((EXPERIMENTS / f"{name}.yaml").read_text())


@pytest.mark.parametrize("name", ["llm-latency", "llm-outage"])
def test_resilient_system_passes(name):
    world = FakeWorld()
    probe, toxi = wire(world)
    r = run_experiment(spec(name), probe, toxi, sleep=lambda s: None)
    assert r.passed, r.failures
    assert world.rolled_back and world.enabled and not world.toxics


def test_hanging_system_fails_outage_hypothesis():
    world = FakeWorld(fail_fast=False)
    probe, toxi = wire(world)
    r = run_experiment(spec("llm-outage"), probe, toxi, sleep=lambda s: None)
    assert not r.passed and any("p95" in f for f in r.failures)
    assert world.enabled  # rollback still happened


def test_no_recovery_is_reported():
    world = FakeWorld(recovers=False)
    probe, toxi = wire(world)
    r = run_experiment(spec("llm-outage"), probe, toxi, sleep=lambda s: None)
    assert any(f.startswith("after rollback") for f in r.failures)
    assert "FAIL" in render([r])


def test_unhealthy_start_aborts_without_injecting():
    world = FakeWorld()
    world.enabled = False
    probe, toxi = wire(world)
    r = run_experiment(spec("llm-latency"), probe, toxi, sleep=lambda s: None)
    assert not r.passed and "aborted" in r.failures[0] and not world.toxics


def test_all_experiment_specs_are_well_formed():
    for path in EXPERIMENTS.glob("*.yaml"):
        s = yaml.safe_load(path.read_text())
        assert {"name", "steady_state", "fault", "hypothesis"} <= set(s), path
        assert s["fault"]["kind"] in ("toxic", "outage")


def test_capacity_plan_uses_littles_law():
    p = plan(target_rps=2, avg_latency_s=8, p95_latency_s=16, per_pod_concurrency=8, headroom=0.25)
    assert p.in_flight_avg == 16 and p.in_flight_p95 == 32
    assert p.pod_replicas == 5  # ceil(32 * 1.25 / 8)
    assert p.hpa_max >= p.pod_replicas
    assert p.model_tokens_per_s == 6000


def test_capacity_floor_is_zone_count():
    p = plan(target_rps=0.1, avg_latency_s=2, p95_latency_s=3)
    assert p.pod_replicas == 3 and any("zone" in n for n in p.notes)


def test_k6_summary_parsing(tmp_path):
    summary = {"metrics": {"http_reqs": {"rate": 1.5},
                           "http_req_duration{endpoint:run}": {"avg": 7500.0, "p(95)": 15000.0}}}
    f = tmp_path / "s.json"
    f.write_text(json.dumps(summary))
    assert from_k6_summary(f) == (1.5, 7.5, 15.0)
