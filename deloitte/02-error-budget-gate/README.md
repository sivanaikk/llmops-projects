# 02 · Error-budget release gate (`budgetgate`, Go)

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"gating production admission on error budgets and automated checks"*,
> *"SLIs, SLOs, SLAs, error budgets"*, Go.

SLOs as code. One YAML spec per SLO ([`slos/`](slos/)) drives three things:

```
slos/agent-runtime.yaml ──► budgetgate rules ──► Prometheus recording rules + multiwindow burn-rate alerts
                        └─► budgetgate check ──► admit / deny a release (exit 0 / 1)
                                                  used by CI (production-gate) and Argo CD (PreSync hook)
```

## The gate's policy

| Situation | Decision |
|---|---|
| budget above `min_budget_remaining`, burn rates within policy | admit |
| budget below minimum, **or** 1h burn > 14.4x, **or** 6h burn > 6x | deny |
| blocked, `--change-type fix --override-ticket CHG-1234` | admit, ticket recorded in the decision |
| blocked, a *feature* with a ticket | deny: tickets only unlock fixes |
| `--change-type rollback` | always admit |
| Prometheus unreachable | deny (`on_error: closed`) or admit with a warning (`open`) |
| no traffic yet | admit |

The gate queries the raw SLI, not the recording rules, so it works on day one
before the rules are deployed. It speaks the Prometheus HTTP API, so it works with
Azure Monitor managed Prometheus, Amazon Managed Prometheus, Thanos or Mimir (bearer token via env).

```bash
go test ./...                                                   # 10 tests incl. a fake Prometheus server
go run ./cmd/budgetgate rules --slos slos                       # -> ../observability/prometheus/rules/slo-generated.yml
go run ./cmd/budgetgate check --slo slos/agent-runtime.yaml --prometheus http://localhost:9090
```

Example decision:
```json
{"service": "agent-runtime", "slo": "availability", "allowed": false,
 "reasons": ["1h burn rate 20.0x exceeds 14.4x: an incident is likely in progress"],
 "budget_remaining": 0.9, "burn_rate_1h": 20, "burn_rate_6h": 3, "checked_at": "..."}
```
