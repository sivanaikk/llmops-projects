# Learn: load testing, chaos engineering and capacity planning

**You'll be able to:** write a load test whose pass/fail comes from the SLOs;
run a chaos experiment with a steady-state hypothesis and a safe rollback;
size a service for long-running requests with Little's law.
**Time:** ~2 h · **Needs:** Python (k6 + Docker for the live labs)

---

## 1. The problem

"It works on my laptop" says nothing about what happens at 5× traffic, when the
model provider adds 3 seconds of latency, or when connections hang forever.
You want to find those answers on a Tuesday afternoon, not during the Friday incident.

## 2. Concepts

**Load testing: open vs closed loop.** A closed-loop test (N users, each waits
for its reply) *slows down when the system slows down*, so it hides queueing.
Real users don't wait for each other. [`k6/agent-load.js`](k6/agent-load.js) uses
**arrival-rate** executors: requests keep arriving at the target rate.

**Thresholds come from the SLOs**, not from guesses:

```js
agent_platform_error: ['rate<0.01'],          // 99% availability SLO
'http_req_duration{endpoint:run}': ['p(95)<20000'],
agent_steps: ['p(95)<=6'],                    // a load test that passes while the agent loops is a fail
agent_cost_usd: ['p(95)<0.01'],
```

**Chaos engineering = a scientific experiment, not breaking things:**

```
1. steady state  measure normal; ABORT if not healthy (don't add chaos to an incident)
2. hypothesis    "with +3s model latency, answers still arrive; p95 < 55s"
3. inject        Toxiproxy toxic between the agent and the model
4. verify        measure again against the hypothesis
5. rollback      ALWAYS (in `finally`)
6. recover       back to steady state by itself?
```

| Experiment | Fault | What a pass proves |
|---|---|---|
| `llm-latency` | +3s per model call | timeouts and deadline are sized right |
| `llm-outage` | model unreachable | the agent **fails fast** (< 10s), it doesn't hang |
| `llm-stall` | connections hang | the run deadline bounds every request |
| `llm-flaky` | 30% connection resets | retries absorb transient errors |

**Little's law: L = λ × W.** Agent runs take seconds, so concurrency, not RPS, is the
limit. 2 req/s × 20s p95 = 40 requests in flight → with 8 per pod and 30% headroom,
7 pods. And the model tier must sustain 2 × 3000 = 6000 tokens/s, usually the real bottleneck.

## 3. Walkthrough

No Docker needed:
```bash
cd ..   # deloitte/
pytest 05-resilience -q                   # the chaos runner against a fake agent + fake Toxiproxy
PYTHONPATH=05-resilience python -m resilience.capacity --avg-latency 8 --p95-latency 20 --target-rps 2
```
Real output (abridged):
```json
{"target_rps": 2.0, "in_flight_avg": 16.0, "in_flight_p95": 40.0, "pod_replicas": 7, "hpa_min": 7, "hpa_max": 25,
 "model_tokens_per_s": 6000.0,
 "notes": ["model backend must sustain ~6,000 tokens/s; CPU-hosted small models do roughly 50-300 tokens/s per node, so scale the model tier, not just the agent pods"]}
```

With Docker (the full lab):
```bash
make up                      # agent -> toxiproxy -> ollama (qwen2.5)
make load RPS=1              # k6 steady + 5x spike; summary.json
make capacity TARGET_RPS=5   # plan from your measured latency
make chaos                   # all four experiments, report in chaos-report.md
```

Read [`resilience/chaos.py`](resilience/chaos.py) `run_experiment`: note the abort before injecting and
the `finally`. Cloud versions: Azure Chaos Studio in
[`../06-platform-azure/terraform/chaos.tf`](../06-platform-azure/terraform/chaos.tf) and an AWS FIS template in
[`cloud/`](cloud/aws-fis-agent-network-latency.json) (note its CloudWatch stop condition).

## 4. Exercises

```bash
make check EX=06      # Little's law, replicas with a zone floor, model-tier load
```

Challenges:
1. Write `experiments/llm-slow-bandwidth.yaml` using Toxiproxy's `bandwidth` toxic. What hypothesis?
2. Add a `soak` analysis: in a 2-hour run, does p95 creep up? What would cause that in this stack?
3. The HPA scales on CPU. Agent pods are mostly *waiting* on the model. Why is CPU a poor signal here,
   and what would you scale on instead? (Hint: in-flight requests; see KEDA or custom metrics.)

## 5. Break it

```bash
make break-it ID=chaos-no-rollback
make break-it ID=chaos-skip-steady-state
make break-it ID=capacity-sized-for-average
```

## 6. Check yourself

<details><summary>1. The outage experiment "passed" with 0% success. How?</summary>

Its hypothesis isn't "requests succeed" (they can't, the model is down). It's "fail fast with
`llm_unavailable`, p95 < 10s, and recover after". A hanging agent would fail the p95 check.
</details>

<details><summary>2. Why size for p95 latency rather than average?</summary>

The slow tail holds worker slots longest. Sized for the average, tail requests queue, latency rises,
more requests pile up: a feedback loop.
</details>

<details><summary>3. Why put the AWS FIS stop condition on an SLO alarm?</summary>

If the experiment starts hurting users more than planned, it stops automatically. Chaos experiments
need a blast-radius limit and a kill switch.
</details>

## 7. In the interview

* "How do you load test an LLM service?" Open-loop arrivals; thresholds from SLOs, including steps and
  cost per run; capacity from Little's law; the model tier as the bottleneck.
* "Describe a chaos experiment." The steady-state → hypothesis → inject → verify → rollback → recover
  loop, using `llm-outage` (fail fast) as the example.

## Go further
* Principles of Chaos Engineering (principlesofchaos.org)
* Grafana k6 docs: "Open and closed models"
