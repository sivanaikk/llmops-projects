# 07 · DevSecOps and the SSDLC

> JD: *"automation across the SSDLC"*, *"CI/CD, DevSecOps, ADO, GitHub, SonarQube"*,
> *"segregation-of-duties controls"*, *"gating production admission on error
> budgets and automated checks"*.

The pipeline is [`.github/workflows/deloitte.yml`](../../.github/workflows/deloitte.yml)
at the repo root. It runs on every push and PR that touches `deloitte/`.

| Stage | Job | What it enforces |
|---|---|---|
| Build & test | `python` | ruff, all Python tests (agent runtime, sentinel, evals, resilience) |
| | `go` | gofmt, `go vet`, `go test -race`, and **generated SLO rules must match the SLO specs** (no hand-edited rules) |
| Validate | `validate` | promtool `check` + alert **unit tests**; `helm lint` + kubeconform; Argo CD manifests against the CRD schemas; `terraform fmt/validate`; `k6 inspect` |
| Secure | `security` | gitleaks (secrets), Trivy (fixable CRITICAL vulns fail the build; IaC misconfig reported), SBOM (SPDX) artifact, SonarQube quality gate when `SONAR_TOKEN` is set ([`sonar-project.properties`](../sonar-project.properties)) |
| Verify behaviour | `agent-evals` | nightly or manual: **real** `qwen2.5:1.5b` vs `qwen2.5:0.5b` through Ollama on the runner; report in the job summary |
| Release | `production-gate` | manual, `main` only. `environment: production` needs an approver other than the author; `budgetgate check` must admit the release |

## Segregation of duties, in layers

| Control | Where |
|---|---|
| Required reviewers on the `production` environment | GitHub environment settings (used by `production-gate`) |
| Code owners for SLO policy, infra and pipelines | [`CODEOWNERS.example`](CODEOWNERS.example) |
| Devs sync dev only; SRE syncs prod; weekend freeze window | [Argo CD AppProject](../06-platform-azure/argocd/project.yaml) |
| Only SRE can start chaos experiments | Azure RBAC on the Chaos Studio experiment ([`chaos.tf`](../06-platform-azure/terraform/chaos.tf)) |
| A blocked release needs a ticket approved outside the pipeline | `budgetgate --change-type fix --override-ticket CHG-####` |

## Azure DevOps

The same stages map 1:1 to an ADO YAML pipeline: environments with approvals
and checks replace GitHub environments, and the budget gate becomes an
*Invoke REST API* or script check on the production environment.

## Local hooks

[`pre-commit-config.yaml`](pre-commit-config.yaml): gitleaks, ruff, terraform fmt, YAML and private-key checks before code leaves the laptop.
