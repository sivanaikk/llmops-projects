# 05 · Resilience: load, chaos, capacity

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"performance, chaos, and resilience testing"*, *"load testing, chaos
> engineering, capacity planning, autoscaling"*, *"k6, JMeter, LoadRunner,
> Azure Chaos Studio, AWS Fault Injector"*.

## Load: [`k6/agent-load.js`](k6/agent-load.js)
Arrival-rate scenarios (`steady`, `spike` 5x, `soak` 2h), so load doesn't back
off when the system slows down. **Thresholds come from the SLOs**: platform-error
rate < 1%, p95 < 20s, p95 steps ≤ 6, p95 cost per run < $0.01, and an abort if
success drops below 80%. A load test that "passes" while the agent loops is a fail here.

## Chaos: [`resilience/chaos.py`](resilience/chaos.py) + [`experiments/`](experiments/)
Toxiproxy sits between the agent and the model (see `docker-compose.yml`).
Each experiment checks the steady state first (aborts if unhealthy, without
injecting), injects the fault, verifies a **hypothesis**, always rolls back, then checks recovery.

| Experiment | Fault | Hypothesis |
|---|---|---|
| `llm-latency` | +3s per model call | still answers; p95 < 55s; no deadline hits |
| `llm-outage` | model unreachable | **fails fast** (p95 < 10s) with `llm_unavailable`, recovers alone |
| `llm-stall` | connections hang | the 60s run deadline bounds every request |
| `llm-flaky` | 30% connection resets | retries absorb it: ≥ 70% success |

Cloud equivalents: Azure Chaos Studio (pod kill + network delay via Chaos Mesh,
in [`06-platform-azure/terraform/chaos.tf`](../06-platform-azure/terraform/chaos.tf)) and
an AWS FIS template ([`cloud/aws-fis-agent-network-latency.json`](cloud/aws-fis-agent-network-latency.json))
with a CloudWatch-alarm stop condition.

## Capacity: [`resilience/capacity.py`](resilience/capacity.py)
Agent requests last seconds, so capacity is about **concurrency** (Little's law:
in-flight = rate × latency). It sizes for p95 latency, floors replicas at the zone
count, derives the HPA max from the spike factor, and reports the tokens/s the
*model tier* must sustain, which is usually the real bottleneck.

```bash
make load RPS=1 && make capacity TARGET_RPS=5
make chaos
pytest 05-resilience     # 9 tests: fake agent + fake Toxiproxy
```
