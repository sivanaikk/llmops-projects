# Runbook: primary provider degraded / degraded-model serving

**Alerts:** `LLMPrimaryProviderDegraded`, `LLMDegradedModelServing`

## What the router does on its own
1. Retries on the same group (`num_retries: 2`).
2. After `allowed_fails: 3`/min a deployment is cooled down for `cooldown_time: 30s` and the `order: 2` deployment takes traffic.
3. If every `chat-small` deployment fails, the group falls back to `chat-tiny` (lower quality).

## Triage
* "Served by backend" panel: what share is on `secondary`?
* Is the primary actually down or only slow? Latency p95 by model. Timeouts count as failures.
* Provider status page (in the lab: `curl ollama-primary:11434/api/tags`; with the mock: `/admin/state`).

## Mitigate
* **Primary down, secondary healthy:** nothing urgent. Watch secondary capacity: its `rpm: 60` quota is half the primary's. If 429s appear, raise the secondary quota (MR to `config.yaml`) or shed non-critical traffic (internal-tools key rpm).
* **Degraded to chat-tiny:** tell feature owners (#team-account-intel) that answers are lower quality. Evals showed chat-tiny loses fact recall on number lookups (see `06-evals-harness` results).
* **Pin traffic away from a flapping provider:** set its deployment `rpm: 0` via MR rather than waiting on cooldown churn.

## Game day
`python 09-sre/tools/game_day.py --scenario primary-outage` reproduces this alert end to end.
