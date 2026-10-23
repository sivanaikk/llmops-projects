# LLMOps Projects

Hands-on LLMOps projects, each built against a real job description. They
apply the ideas from the [LLM Inference at Scale](https://github.com/sivanaikk/llm-inference-at-scale)
handbook (serving, metrics, caching, cost, routing) to the platform side of
running LLMs: gateways, guardrails, agents, observability, evals and SRE.

**Small models only.** Every project runs on sub-2B-parameter models through
[Ollama](https://ollama.com) on a laptop CPU (Qwen2.5-0.5B/1.5B, SmolLM2-360M,
all-MiniLM). The point is the operational machinery around the model, not the
model itself. Swapping in a hosted provider is a one-line change in the
gateway config.

| Company | Role | Folder | What gets built |
|---|---|---|---|
| Demandbase | DevOps Engineer, AI Runtime Services | [`demandbase/`](demandbase/) | LLM gateway (LiteLLM) with failover and quotas, guardrails, semantic cache, cost attribution, LLM observability, eval harness with CI gate, EKS/Karpenter/Flux infra, SLOs and runbooks |
| Deloitte USI | Applied AI Site Reliability Engineer III | [`deloitte/`](deloitte/) | Bounded tool-using agent runtime, SLOs-as-code + error-budget release gate (Go), drift & cost-anomaly sentinel, agent evals with MLflow, k6 + Toxiproxy chaos + capacity planning, AKS/Azure OpenAI/Chaos Studio in Terraform, Helm + Argo CD with segregation of duties, DevSecOps GitHub Actions |

## Layout convention

```
llmops-projects/
└── <company>/
    ├── README.md        # JD -> project mapping, architecture, quickstart
    ├── 01-.../          # one numbered folder per project, each with its own README and tests
    └── docker-compose.yml, Makefile, CI (GitLab for demandbase, GitHub Actions for deloitte)
```
