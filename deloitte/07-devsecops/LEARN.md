# Learn: DevSecOps for AI services

**You'll be able to:** design a pipeline where each stage blocks a specific
class of problem; secure the CI supply chain itself; put real-model evals in CI
without making it slow or flaky; build a production gate with segregation of duties.
**Time:** ~1.5 h · **Needs:** a GitHub fork of this repo (to see Actions run)

---

## 1. The problem

AI services add new things that can break a release: a prompt edit, a model
version, an eval threshold. They also keep all the old ones: vulnerable
dependencies, leaked keys, bad Terraform. Each needs an automated check at the
right stage, or it reaches production.

## 2. Concepts

The workflow ([`/.github/workflows/deloitte.yml`](../../.github/workflows/deloitte.yml)), stage by stage:

| Stage | Blocks | Example |
|---|---|---|
| `python`, `go` | broken code | ruff, pytest, `go test -race` |
| `go` | **generated-file drift** | regenerate SLO rules and `diff` against the committed file |
| `validate` | broken infra/alerts | promtool alert unit tests, helm + kubeconform, Argo CD CRD schemas, terraform validate, k6 inspect |
| `security` | supply-chain risk | gitleaks (secrets), Trivy (fixable CRITICAL vulns fail), Trivy config (IaC), SBOM, SonarQube |
| `agent-evals` | quality regressions | real qwen2.5 models via Ollama on the runner; report in the job summary |
| `production-gate` | risky releases | GitHub environment with required reviewers + `budgetgate check` |

**Securing the pipeline itself.** The first CI run failed because
`aquasecurity/trivy-action@0.28.0` no longer resolved, and GitHub resolves every
action when a job starts, even ones in skipped steps. The fix ran Trivy, Syft and
the Sonar scanner from **pinned container images** instead. Fewer third-party actions
with access to your workspace and token is also a smaller supply-chain attack surface.
(Going further: pin actions to commit SHAs, and use `permissions: contents: read` by default, as this workflow does.)

**Real-model evals in CI without slowing every push.** They take ~6–9 minutes on a
CPU runner, so they run nightly, on manual dispatch, and on any push whose commit
message contains `[run-evals]`. A promotion-gate failure is a warning annotation,
because the job compares two candidates; the *production* gate is what blocks a release.

**Segregation of duties**, in layers ([README](README.md#segregation-of-duties-in-layers)): environment
reviewers, CODEOWNERS on policy files, Argo CD roles, RBAC on chaos, ticketed overrides.

## 3. Walkthrough

1. Fork the repo and push a commit touching `deloitte/`. Watch the jobs in the Actions tab.
2. Make CI fail on purpose (pick one, then revert):
   * change `objective: 0.99` → `0.995` in `02-error-budget-gate/slos/agent-runtime.yaml` → the `go` job's
     "Generated SLO rules are up to date" step fails
   * add `aws_secret = "AKIA` + 16 capital letters + `"` to any file → gitleaks fails
3. Push with `[run-evals]` in the message and read the eval report in the job summary.

Locally, the same checks: `make test lint validate`, plus [`pre-commit-config.yaml`](pre-commit-config.yaml).

## 4. Exercises (open-ended)

1. **Pin every action to a commit SHA** (keep the version in a comment). Why is a tag not enough?
2. **Make the eval job decisive on PRs:** when a PR changes `agentops/agent.py` or a prompt, run
   baseline-from-`main` vs candidate-from-PR and *fail* on a gate regression. What makes this hard on a 2-vCPU runner?
3. **Translate to Azure DevOps:** write the `production-gate` stage as an ADO environment with an approval
   check and a script check running `budgetgate`.

## 5. Check yourself

<details><summary>1. Trivy finds a CRITICAL vulnerability with no fixed version. Should the build fail?</summary>

This pipeline uses `--ignore-unfixed`: failing on something nobody can fix yet trains people to bypass
the scanner. Track it (SBOM, report) and fail as soon as a fix exists. Some regulated environments
choose differently and document the risk acceptance instead.
</details>

<details><summary>2. Why diff generated files in CI instead of generating them at deploy time?</summary>

The committed file is what reviewers read and what Git history records. Regenerating and diffing
guarantees that what was reviewed is what gets deployed, and catches "edited the spec, forgot to regenerate".
</details>

<details><summary>3. Why is a failed eval gate only a warning in the `agent-evals` job?</summary>

That job compares a *candidate* config with the baseline on a schedule; a candidate losing is information,
not a broken build. Blocking belongs where a change is about to be released (the PR or the production gate).
</details>

## 6. In the interview

* "Walk me through your CI/CD for an AI service." The stage table, plus what's AI-specific: eval gates,
  prompt changes as deploys, model versions pinned.
* "Tell me about a pipeline failure you fixed." The unresolvable Trivy action, and moving to pinned images.

## Go further
* SLSA framework (slsa.dev): supply-chain levels
* GitHub docs: "Security hardening for GitHub Actions"
