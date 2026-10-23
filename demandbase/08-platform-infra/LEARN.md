# Learn: EKS, Karpenter, Flux and Terraform for an AI runtime

**You'll be able to:** read Terraform for a production-shaped EKS cluster;
explain node pools for latency-critical vs interruptible workloads; run a
GitOps flow where CI never touches the cluster; keep generated config in sync.
**Time:** ~1.5 h · **Needs:** terraform, kustomize, kubeconform (no AWS account needed)

---

## 1. The problem

The gateway is tier-1: if it's down, every AI feature is down. Its infrastructure
needs to be reproducible (Terraform), self-healing (GitOps), cost-aware (spot where
safe) and impossible to change by hand without anyone noticing.

## 2. Concepts

**Terraform ([`terraform/`](terraform/))**: VPC across 3 AZs, EKS with a small *tainted*
system node group, Karpenter for everything else, RDS Postgres (gateway keys and spend),
ElastiCache Redis (rate limits, cooldowns, cache), and Secrets Manager.

**Two Karpenter NodePools**, by how much interruption a workload tolerates:

| NodePool | Capacity | Disruption | Why |
|---|---|---|---|
| `gateway` | on-demand only | one node at a time | the front door: no spot reclaim at peak |
| `model-cpu` | spot + on-demand, Graviton | consolidate when idle | model servers sit behind gateway failover, so losing one is OK |

**GitOps with Flux:** CI builds the image and commits the new tag to
`gitops/apps/dev/kustomization.yaml`. Flux applies it, and a `healthChecks` entry on the
gateway Deployment gates the rollout. CI holds no cluster credentials.

**One source of truth for alerts:** `scripts/gen_prometheus_rule.py` wraps
`05-llm-observability/prometheus/rules/slo-alerts.yml` in a PrometheusRule CR. CI runs it
with `--check` and fails on drift, so local and in-cluster alerting can't disagree.

## 3. Walkthrough

```bash
cd 08-platform-infra/terraform && terraform init -backend=false && terraform validate
cd .. && kustomize build gitops/apps/dev | kubeconform -strict -ignore-missing-schemas -summary
python scripts/gen_prometheus_rule.py --check     # "prometheus-rule.yaml up to date"
```

Then trace a release: `.gitlab-ci.yml` `build-gateway` → `bump-dev-tag` → `gitops/clusters/dev/apps.yaml`
(Flux Kustomization with `dependsOn` and `healthChecks`) → `gitops/apps/base/ai-runtime/gateway.yaml`.

## 4. Exercises (open-ended)

1. **Add a prod overlay** (`gitops/apps/prod`) with 3 replicas, `minAvailable: 2`, and a different image-tag
   policy. How does a change get promoted from dev to prod without someone editing YAML by hand?
2. **Drift drill:** change the alert YAML without regenerating, run `gen_prometheus_rule.py --check`, then fix it.
3. **Cost:** the dev cluster runs a NAT gateway and two system nodes 24/7. Estimate the monthly floor and propose
   two savings that don't hurt the gateway's reliability.

## 5. Check yourself

<details><summary>1. Why is the system node group tainted?</summary>

So only critical add-ons and Karpenter run there. Application pods go to Karpenter-managed pools, and
a noisy workload can't starve CoreDNS or the autoscaler itself.
</details>

<details><summary>2. Why doesn't CI run kubectl apply?</summary>

Git becomes the single record of what's deployed; the cluster pulls changes (no CI credentials in the cluster);
rollbacks are git reverts; and drift (manual changes) is detected and reverted by the controller.
</details>

## 6. In the interview

* "How do you run a tier-1 service on Kubernetes cost-effectively?" Separate node pools by interruption
  tolerance, PDBs, zone spread, and spot only behind failover.
* "What's your GitOps flow?" CI → tag bump commit → Flux reconcile → health-check-gated rollout.

## Go further
* terraform-aws-modules/eks and the Karpenter docs (NodePool disruption budgets)
* Flux docs: Kustomization `healthChecks` and `dependsOn`
