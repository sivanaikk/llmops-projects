# Learn: the platform: AKS, Helm, Argo CD and controls that hold

**You'll be able to:** read and validate Terraform for AKS and Azure AI services;
explain what each Helm security setting protects against; set up Argo CD so
manual changes are reverted (drift prevention) and production needs the right
people (segregation of duties); hook the error-budget gate into deployments.
**Time:** ~2 h · **Needs:** terraform, helm, kubeconform (no Azure account needed)

---

## 1. The problem

Reliability and security controls that live in a wiki get skipped under
pressure. They have to live where the change happens: in Terraform, in the
chart, and in the deployment controller.

## 2. Concepts

**Terraform ([`terraform/`](terraform/))**: what each choice buys you:

| Setting | Why |
|---|---|
| `workload_identity_enabled`, `local_account_disabled`, Entra RBAC | no long-lived keys or shared kubeconfigs: identities, not secrets |
| `local_auth_enabled = false` on Azure OpenAI | API keys can't leak because there aren't any |
| Azure Monitor workspace + `monitor_metrics {}` | managed Prometheus: the same PromQL SLO rules work in the cloud |
| `daily_quota_gb` on Log Analytics in dev | log cost can't run away in a sandbox |
| spot workload pool in dev, regular in prod | cheap where interruptions are acceptable |
| `capacity` on the OpenAI deployment | the provider quota the gateway must respect (TPM) |
| Chaos Studio + RBAC for the SRE group only | fault injection is a privileged operation |

**Helm chart ([`helm/agent-runtime/`](helm/agent-runtime/))**, by template:

* `deployment.yaml`: non-root, read-only root filesystem, all capabilities dropped; readiness checks
  the **model path** (`/readyz`); `terminationGracePeriodSeconds` = run deadline + 15s so in-flight runs finish;
  zone spread; `maxUnavailable: 0` rollouts
* `hpa-pdb.yaml`: autoscaling plus a disruption budget so node drains don't take everything down
* `networkpolicy.yaml`: **egress allowlist** (DNS, model, telemetry, gateway). An agent executes
  model-chosen actions, so it shouldn't be able to reach the internet.
* `budget-gate-hook.yaml`: an Argo CD **PreSync** Job running `budgetgate check`. If it exits 1, the sync fails and nothing rolls out.

**Argo CD ([`argocd/`](argocd/))**:

| Control | How |
|---|---|
| Drift prevention | `selfHeal: true`: a manual `kubectl edit` is reverted to git within minutes |
| Safe prod deletes | prod `prune: false`: a human confirms deletions |
| Segregation of duties | AppProject roles: developers sync dev only, SRE syncs prod |
| Change freeze | `syncWindows` deny prod Friday 12:00 → 60h, `manualSync: true` for incident fixes |
| Guardrails for app teams | no cluster-scoped resources; orphaned resources reported |

## 3. Walkthrough

```bash
cd terraform && terraform init -backend=false && terraform validate     # Success! The configuration is valid.
cd ../helm && helm lint agent-runtime
helm template rel agent-runtime | kubeconform -strict -summary -ignore-missing-schemas
# Summary: 9 resources found parsing stdin - Valid: 8, Invalid: 0, Errors: 0, Skipped: 1
helm template rel agent-runtime --show-only templates/budget-gate-hook.yaml
```

Render with dev values and diff to see what changes per environment:
```bash
helm template rel agent-runtime --set budgetGate.enabled=false --set replicaCount=1 --set autoscaling.enabled=false > /tmp/dev.yaml
helm template rel agent-runtime > /tmp/prod.yaml && diff /tmp/dev.yaml /tmp/prod.yaml
```

## 4. Exercises (open-ended)

1. **Policy as code:** write a test (Python or a Conftest/OPA rule) that fails if the rendered Deployment
   lacks `readOnlyRootFilesystem: true` or a `readinessProbe`. Add it to CI. Today nothing in the
   break-it catalogue covers this chart. Your test would be the safeguard.
2. **Gate the Ollama rollout too.** The model StatefulSet changes rarely but is risky. Should the
   PreSync gate cover it? What about the init container that downloads models: what if the registry is down?
3. **Azure OpenAI behind the gateway:** set `enable_azure_openai = true` mentally, and write the LiteLLM
   `model_list` entry (Track A [01-llm-gateway](../../demandbase/01-llm-gateway/LEARN.md)) that uses workload
   identity instead of an API key.

## 5. Check yourself

<details><summary>1. Someone hot-fixes prod with kubectl edit at 2am. What happens, and is that good?</summary>

Argo CD self-heal reverts it to git within minutes. That's good for drift prevention, but an
on-call engineer needs to know it will happen: the real fix is a git commit (with Argo CD's manual sync allowed during the freeze window).
</details>

<details><summary>2. Why is the grace period longer than the run deadline?</summary>

On a rollout or scale-down, the pod gets SIGTERM. If it's killed before in-flight agent runs finish
(up to the 60s deadline), users get errors from a routine deploy.
</details>

<details><summary>3. Why `local_auth_enabled = false` on Azure OpenAI?</summary>

With key auth off, the only way in is an Entra identity (workload identity for pods). There's no key
to leak in a repo, a log or a pipeline variable.
</details>

## 6. In the interview

* "How do you prevent config drift?" GitOps self-heal, generated files diffed in CI, Terraform plan in a
  scheduled job.
* "How do you implement segregation of duties in delivery?" Argo CD project roles, GitHub environment
  reviewers, CODEOWNERS on policy files, RBAC on chaos tooling.

## Go further
* AKS baseline architecture (Azure Architecture Center)
* Argo CD docs: Projects, Sync Windows, Resource Hooks
