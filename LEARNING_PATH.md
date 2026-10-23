# Learning path: LLMOps and Applied AI SRE

These projects were built against two real job descriptions. They are written
so you can **learn** from them, not just read them: every module has a lesson
(`LEARN.md`), auto-checked exercises, and a "break it" lab that injects a real
bug so you can see which safeguard catches it.

Everything runs on **small local models** (Qwen2.5 0.5B/1.5B, SmolLM2 360M,
all-MiniLM). Most of the course needs **no GPU and no Docker**. Only the
full-stack labs at the end of each track use Docker.

## The learning loop (same in every module)

```
 1. Read      LEARN.md: the problem, the concepts, the maths            ~15 min
 2. Run       the walkthrough commands (real output shown so you can compare)
 3. Build     the exercise: make check EX=NN until it passes            ~20-40 min
 4. Break     make break-it ID=...: predict what catches the bug, then run it
 5. Check     answer the self-check questions before opening the answers
 6. Explain   the "In the interview" prompts: say it out loud in 2 minutes
```

## Setup (once)

```bash
git clone https://github.com/sivanaikk/llmops-projects && cd llmops-projects
python3 -m venv .venv && source .venv/bin/activate
pip install -r demandbase/requirements-dev.txt -r deloitte/requirements-dev.txt
# Go 1.22+ for the budget-gate module; promtool (from a Prometheus release) for alert tests
```

Sanity check: `cd deloitte && make test` and `cd demandbase && make test` should both pass.

## Tracks

**Track A: LLM platform engineering** (`demandbase/`): the shared runtime every AI feature runs on.
**Track B: Applied AI SRE** (`deloitte/`): running agents reliably, SLOs, release gates, resilience.

Do them in this order. Track B reuses ideas from Track A, and each stage builds on the previous one.

| # | Stage | Module | You'll learn | Exercise | Docker? |
|---|---|---|---|---|---|
| 1 | Foundations | [B · 08 SRE operations](deloitte/08-sre-operations/LEARN.md) | SLIs, SLOs, error budgets, error-budget policy | (reading + self-check) | no |
| 2 | | [B · 02 Error-budget gate](deloitte/02-error-budget-gate/LEARN.md) | burn rates, multiwindow alerts, SLOs as code, release gating (Go) | B-07 (Go) | no |
| 3 | | [A · 05 LLM observability](demandbase/05-llm-observability/LEARN.md) | metrics vs traces, cardinality, LLM latency/TTFT, alert unit tests | A-03, A-06 | no |
| 4 | The gateway | [A · 01 LLM gateway](demandbase/01-llm-gateway/LEARN.md) | model groups, routing, retries, cooldowns, fallbacks, quotas, virtual keys | (e2e lab) | no |
| 5 | | [A · 02 Guardrails](demandbase/02-guardrails/LEARN.md) | PII detection with checksums, injection scoring, per-team policy | A-01 | no |
| 6 | | [A · 03 Semantic cache](demandbase/03-semantic-cache/LEARN.md) | exact vs semantic caching, scoping, thresholds from data | A-02 | no |
| 7 | | [A · 04 Cost control](demandbase/04-cost-control/LEARN.md) | attribution, shadow pricing, showback, burn-rate budgeting | A-04 | no |
| 8 | Quality | [A · 06 Evals harness](demandbase/06-evals-harness/LEARN.md) | eval design, LLM-as-judge, statistical regression gates | A-05 | no |
| 9 | | [A · 07 RAG app](demandbase/07-account-rag-app/LEARN.md) | building a feature *on* a platform; retrieval vs generation failures | (challenges) | no |
| 10 | Agents | [B · 01 Agent runtime](deloitte/01-agent-runtime/LEARN.md) | agent failure modes, budgets, retries, circuit breakers, guards in code | B-01, B-02, B-03 | no |
| 11 | | [B · 04 Agent evals](deloitte/04-agent-evals/LEARN.md) | trajectory evals, pass@1 vs pass^k, experiment tracking | B-05 | no |
| 12 | | [B · 03 Drift & cost sentinel](deloitte/03-drift-cost-sentinel/LEARN.md) | PSI, JS divergence, robust z-scores, effect size | B-04 | no |
| 13 | Resilience | [B · 05 Resilience](deloitte/05-resilience/LEARN.md) | load testing, chaos experiments, Little's law | B-06 | optional |
| 14 | | [A · 09 SRE (gateway)](demandbase/09-sre/LEARN.md) | runbooks, game days, postmortems | (game day) | optional |
| 15 | Platform | [A · 08 Platform infra](demandbase/08-platform-infra/LEARN.md) | EKS, Karpenter, Flux GitOps, Terraform | (challenges) | no |
| 16 | | [B · 06 Platform on Azure](deloitte/06-platform-azure/LEARN.md) | AKS, Helm, Argo CD, drift prevention, segregation of duties | (challenges) | no |
| 17 | | [B · 07 DevSecOps](deloitte/07-devsecops/LEARN.md) | SSDLC pipeline, supply chain, SBOM, production gates | (challenges) | no |
| 18 | Capstone | both `docker-compose.yml` stacks | run everything on real small models; game days; real evals | | **yes** |

Rough time: about 2 hours per module, about 30 hours for the whole path.

## Tools that work in every module

| Command (run inside `deloitte/` or `demandbase/`) | What it does |
|---|---|
| `make exercises` | run every exercise against *your* code in `exercises/starter/` |
| `make check EX=03` | check one exercise |
| `make solutions` | run the tests against the reference solutions (peek only after trying) |
| `make break-it` | list the bug catalogue for this lab |
| `make break-it ID=<id>` | inject that bug into a temp copy and run the safeguard that should catch it |
| `python -m agentops.demo` (in `deloitte/01-agent-runtime`) | watch the agent loop step by step, no model needed |
| `make sentinel-demo` (deloitte) / `make cache-bench`, `make showback DEMO=1` (demandbase) | concept demos on synthetic data |

`make break-it` is the best way to see why each safeguard exists. Before every
run, **predict** which test or alert will fail and why. All 32 bugs in the two
catalogues are verified to be caught (CI runs `break_it.py --all`).

## What's real and what's simulated

* **Real:** all code, tests, alert rules, Terraform, Helm and Argo CD manifests; the
  LiteLLM gateway e2e (a real proxy with mock providers); the agent evals in CI
  (real Qwen models through Ollama on GitHub runners; see
  [the eval history](deloitte/04-agent-evals/README.md#eval-history-real-runs-in-ci-qwen25-on-a-2-vcpu-github-runner-12-tasks--2-trials)).
* **Simulated:** company data (fictional accounts and services), cloud accounts
  (Terraform validates but isn't applied), drift/cost scenarios (synthetic generators).

## Glossary

See [GLOSSARY.md](GLOSSARY.md) for every term used across the modules.
