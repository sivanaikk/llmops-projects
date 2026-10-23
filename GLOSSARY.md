# Glossary

| Term | Meaning | Where it's used |
|---|---|---|
| **SLI** | Service level *indicator*: a measured ratio of good events to all events (e.g. agent runs that didn't fail for platform reasons). | B-08, B-02 |
| **SLO** | Service level *objective*: the target for an SLI over a window (99% over 28 days). | B-08, B-02 |
| **SLA** | A contractual promise to a customer, usually looser than the SLO, with penalties. | B-08 |
| **Error budget** | `1 - SLO`: the amount of failure you are allowed. 99% → 1% of events may fail. | B-02 |
| **Burn rate** | How fast the budget is being spent: `error_ratio / error_budget`. 1 = exactly on budget; 14.4 for 1 hour spends 2% of a 30-day budget. | B-02, A-05 |
| **Multiwindow alert** | Fire only if a long window (proves it's significant) **and** a short window (proves it's still happening) both burn fast. | B-02, A-05 |
| **Release gate** | An automated check that blocks a deploy, here when the error budget is low or burning fast. | B-02 |
| **Cardinality** | The number of distinct label combinations of a metric, i.e. the number of time series stored. | A-05 |
| **TTFT** | Time to first token: what a streaming user experiences as responsiveness. | A-05 |
| **Model group** | A gateway alias (`chat-small`) that maps to one or more real deployments. Callers never name providers. | A-01 |
| **Cooldown** | The gateway temporarily removes a deployment after repeated failures. | A-01 |
| **Fallback** | When every deployment of a group fails, route to another group (often a cheaper or lower-quality model). | A-01 |
| **Virtual key** | A gateway-issued API key tied to a team, with budget and rate limits. | A-01, A-04 |
| **Shadow price** | A reference price attached to self-hosted model usage so showback isn't $0. | A-04 |
| **Showback** | Reporting spend per team/feature without actually charging them (chargeback does charge). | A-04 |
| **Guardrail** | A check on model input/output: PII, prompt injection, policy. | A-02 |
| **Luhn / Verhoeff / mod-97** | Checksums for card numbers / Aadhaar / IBAN. They separate real identifiers from look-alike digit strings. | A-02 |
| **Semantic cache** | Return a cached answer for a *similar* (not identical) question, using embeddings. | A-03 |
| **False hit** | A semantic cache returning an answer to a *different* question. | A-03 |
| **pass@1** | Average share of trials that pass. | B-04 |
| **pass^k** | Share of tasks that pass in *all* k trials, i.e. reliability. | B-04 |
| **Trajectory eval** | Checking how an agent got its answer (tools used, steps, outcome), not just the text. | B-04 |
| **LLM-as-judge** | Using a model to grade outputs on qualities string checks can't see (faithfulness). | A-06 |
| **Bootstrap CI** | A confidence interval made by resampling the data, used to tell real regressions from noise. | A-06 |
| **PSI** | Population Stability Index: a drift score between two distributions. <0.1 stable, >0.25 significant. | B-03 |
| **JS divergence** | Jensen-Shannon divergence: symmetric, bounded (0-1) difference between categorical distributions. | B-03 |
| **Robust z-score** | z-score using median and MAD instead of mean and stdev, so past outliers don't hide new ones. | B-03 |
| **Circuit breaker** | Stops calling a failing dependency for a while; probes it again later. | B-01 |
| **Full jitter** | Random backoff in `[0, cap]` so many clients don't retry in lock-step. | B-01 |
| **Deadline** | One time budget for a whole request, shared by every hop inside it. | B-01 |
| **Little's law** | `L = λ × W`: requests in flight = arrival rate × time in system. | B-05 |
| **Steady-state hypothesis** | In chaos engineering, the measurable "normal" you check before, during and after a fault. | B-05 |
| **GitOps** | Git is the source of truth for what runs; a controller (Flux, Argo CD) makes the cluster match it. | A-08, B-06 |
| **Drift (infra)** | The cluster no longer matches git, e.g. because of a manual `kubectl edit`. Self-heal reverts it. | B-06 |
| **Segregation of duties** | The person who makes a change is not the only one who can approve and release it. | B-06, B-07 |
| **SBOM** | Software bill of materials: the list of everything that went into a build. | B-07 |
| **Toil** | Manual, repetitive, automatable work that grows with the service. | B-08 |
