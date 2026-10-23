# Game day: primary provider outage (lab exercise)

> A **planned exercise** for the local lab using `09-sre/tools/game_day.py`,
> written up with the postmortem template to practise the format. It is not a
> production incident. Fill in the "Observed" column when you run it.

| | |
|---|---|
| Scenario | `primary-outage`: `ollama-primary` returns 503 for 100% of calls for 10 minutes |
| Hypothesis | Chat users see no errors; traffic shifts to the secondary within one cooldown window; `LLMPrimaryProviderDegraded` fires; nobody is paged |
| Detection | `LLMPrimaryProviderDegraded` (ticket) |

## Expectations
| Expectation | How to check | Observed |
|---|---|---|
| No user-visible chat errors | `game_day.py` prints the error rate during the fault | Verified with mock providers by `01-llm-gateway/e2e/run_e2e.py` ("failover to secondary when primary is down") |
| Traffic shifts within ~30s | Grafana "Served by backend": `secondary` takes over | |
| Ticket, no page | Error ratio stays under 14.4 x 0.5% | |
| Embeddings unaffected | `game_day.py` embedding probe | **Expected to fail:** see finding 1 |

## Findings (from walking the scenario through `01-llm-gateway/config.yaml`)
| # | Finding | Action | Type |
|---|---|---|---|
| 1 | `embed-small` has a single deployment, on the primary. A primary outage takes RAG retrieval down even though chat fails over. | Add an `embed-small` deployment on the secondary. It must be the **same** embedding model, or vectors in the index stop being comparable. | prevent |
| 2 | Availability alerts use the global error ratio. A small model group (embeddings) can be 100% down while the global ratio looks healthy. | Add a per-model-group burn-rate alert. | detect |
| 3 | The secondary's `rpm: 60` is half the primary's quota. A long primary outage at peak will 429. | Load-test the failover path with `tools/loadgen.py` and size the secondary quota from the result. | mitigate |

Findings 1 and 2 are left unfixed in `config.yaml` on purpose: running the
game day should surface them.
