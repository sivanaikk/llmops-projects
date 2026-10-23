# 09 · SRE: SLOs, on-call, incidents

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"SLOs, on-call, incident response, and the postmortems for the runtime.
> This is a genuine SRE ownership role."*

| | |
|---|---|
| [`slos.md`](slos.md) | SLIs/SLOs for the gateway (availability 99.5%, latency, attribution coverage), alert policy, error-budget policy |
| [`runbooks/`](runbooks/) | One runbook per alert: [gateway errors](runbooks/gateway-errors.md), [provider failover](runbooks/provider-failover.md), [latency](runbooks/gateway-latency.md), [cost spike](runbooks/cost-spike.md), [guardrail spike](runbooks/guardrail-spike.md) |
| [`postmortems/TEMPLATE.md`](postmortems/TEMPLATE.md) | Blameless postmortem template |
| [`postmortems/2026-10-gameday-primary-provider-outage.md`](postmortems/2026-10-gameday-primary-provider-outage.md) | Game-day plan and findings for a primary-provider outage, including two real gaps found by walking the scenario through the config (single-deployment embeddings; global-only error ratio) |
| [`tools/game_day.py`](tools/game_day.py) | Fault injection against the compose stack: `primary-outage`, `secondary-outage`, `slow-provider`, `redis-outage` |
| [`tools/loadgen.py`](tools/loadgen.py) | Open-loop (Poisson) load generator → throughput, error rate by code, p50/p95/p99 |

```bash
make gameday SCENARIO=primary-outage   # watch Grafana + localhost:9090/alerts meanwhile
make load RPS=3 DURATION=60
```
