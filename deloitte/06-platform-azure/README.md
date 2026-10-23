# 06 · Platform: Azure, Terraform, Kubernetes, Argo CD

> JD: *"Azure, Azure OpenAI"*, *"Kubernetes, Docker, Terraform, ArgoCD"*,
> *"drift prevention"*, *"access controls"*.

## Terraform ([`terraform/`](terraform/), `terraform validate` clean on azurerm 4.x)
| File | |
|---|---|
| `main.tf` | resource group, Log Analytics (daily cap in dev), **Azure Monitor workspace** (managed Prometheus), App Insights (OTel traces), ACR, Key Vault (RBAC) |
| `aks.tf` | AKS: workload identity + OIDC, Entra RBAC, local accounts off, Azure Policy, Cilium network policy, managed Prometheus, Key Vault CSI, auto-upgrade with maintenance window; zonal **spot** workload pool in dev |
| `openai.tf` | optional Azure OpenAI account (`local_auth_enabled = false`: Entra only, no keys) + `gpt-4o-mini` deployment with a TPM quota |
| `chaos.tf` | **Azure Chaos Studio** target and capabilities on AKS, experiment (agent pod-kill + 3s model latency), RBAC so only SRE can start it |

## Helm chart ([`helm/agent-runtime/`](helm/agent-runtime/))
Deployment (non-root, read-only rootfs, dropped caps, zone spread, readiness on
the model path, grace period longer than the run deadline), HPA, PDB,
**egress NetworkPolicy** (DNS, model backend, telemetry, gateway only),
ServiceMonitor, an in-cluster Ollama StatefulSet that pulls the small models, and
the **budget-gate PreSync hook Job**: a denied gate fails the Argo CD sync.

## Argo CD ([`argocd/`](argocd/))
* `project.yaml`: **segregation of duties** (developers sync dev only, SRE syncs prod),
  a Friday-to-Sunday prod deny window that still allows manual SRE syncs,
  no cluster-scoped resources from app teams, orphaned-resource warnings.
* `agent-runtime-dev`: auto-sync with prune and self-heal; the gate is off.
* `agent-runtime-prod`: self-heal (**drift prevention**: manual `kubectl` edits are reverted)
  but no auto-prune; the gate is on; sync retries; Teams notification on failed syncs.

```bash
helm lint helm/agent-runtime && helm template rel helm/agent-runtime | kubeconform -strict -ignore-missing-schemas
cd terraform && terraform init -backend=false && terraform validate
```
