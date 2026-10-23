# 08 · Platform infrastructure: AWS EKS, Terraform, Karpenter, Flux

> JD: *"Strong production infrastructure background: Kubernetes, AWS,
> Terraform, GitOps"* and the stack *"EKS, Flux/GitOps, Karpenter"*.

## Terraform ([`terraform/`](terraform/))

| File | Creates |
|---|---|
| `vpc.tf` | VPC across 3 AZs, private/public/database subnets, single NAT in dev; subnets tagged for Karpenter discovery |
| `eks.tf` | EKS 1.31, a small tainted **system** node group (Graviton) for add-ons and Karpenter; EBS CSI via IRSA |
| `karpenter.tf` | Karpenter IAM/SQS (pod identity) + Helm release |
| `data-stores.tf` | RDS Postgres (LiteLLM keys/teams/spend), ElastiCache Redis (rate limits, cooldowns, cache), Secrets Manager secret with the master key + connection strings |

`terraform validate` passes against the pinned module versions (lock file
committed). Remote state config is stubbed in `versions.tf`.

## GitOps with Flux ([`gitops/`](gitops/))

```
clusters/dev/            Flux Kustomizations: infrastructure → ai-runtime (dependsOn + healthCheck on the gateway)
infrastructure/          Helm repos, kube-prometheus-stack, external-secrets, Karpenter NodePools
apps/base/ai-runtime/    gateway Deployment/Service/HPA/PDB/ServiceMonitor, 2x Ollama StatefulSets,
                         ExternalSecret, PrometheusRule (generated from 05's alert rules)
apps/dev/                overlay: image tag, smaller HPA floor
```

* **Two Karpenter NodePools**: `gateway` is on-demand only, with a disruption
  budget of one node at a time, because the gateway is the front door. `model-cpu`
  allows spot plus on-demand Graviton, because the gateway fails over between model servers.
* **Gateway pods**: `maxUnavailable: 0` rollouts, zone spread, PDB, `preStop`
  drain and a 90s grace period so in-flight generations finish.
* **No `kubectl` from CI.** CI builds the image and commits the new tag to
  `apps/dev/kustomization.yaml`. Flux applies it, and the Kustomization health
  check gates the rollout.
* **One source of truth for alerts**: `scripts/gen_prometheus_rule.py` wraps
  `05-llm-observability/prometheus/rules/slo-alerts.yml` in a `PrometheusRule`.
  CI fails if the generated file drifts.

Assumed but not included: a `ClusterSecretStore` named `aws-secrets-manager`,
and ClickHouse plus an OTel collector in an `observability` namespace.

```bash
make validate   # promtool, kustomize|kubeconform, terraform validate/fmt
```
