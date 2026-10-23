# Learn: operating a tool-using agent reliably

**You'll be able to:** name the ways agents fail in production; bound each one
(steps, cost, tokens, deadline, retries, circuit breakers, loop detection);
decide what belongs in the prompt and what belongs in code; instrument an agent
so its failures show up on a dashboard.
**Time:** ~2.5 h · **Needs:** Python only (Ollama optional for the real model)

---

## 1. The problem

A web request makes one call to one backend. An agent run makes **N model calls
and M tool calls**, and the model decides N and M. Every weakness compounds:

```
user question
  └─ step 1: model ─► tool A ─► observation
  └─ step 2: model ─► tool A again (same args)       ← loop
  └─ step 3: model ─► "Sure! here's the answer :)"   ← broke the output format
  └─ step 4: model ─► (provider 503)                 ← flaky dependency
  └─ ...                                             ← cost and latency climbing
```

Nothing here raises an exception by default. The run just gets slow, expensive or wrong.

## 2. Concepts: one bound per failure mode

| Failure mode | Bound | Code |
|---|---|---|
| too many model calls / loops | `max_steps`; loop detection on identical `(tool, args)` | `agent.py` `run` |
| runaway spend | `max_cost_usd`, `max_total_tokens` (shadow-priced for local models) | `agent.py` |
| hangs | one **Deadline** for the whole run; every hop gets `min(own timeout, time left)` | `resilience.py` |
| flaky provider | retry **only** retryable errors (429/5xx/timeouts), full-jitter backoff | `llm.py`, `agent.py` `_call_llm` |
| flaky tool | per-tool timeout + **circuit breaker**; retry only idempotent tools | `tools.py` |
| bad output format | JSON mode + tolerant parser + corrective re-prompt, capped | `agent.py` `parse_action` |
| claims actions it can't take | **code** pre-check (refuse change requests) + post-check (replace false claims) | `agent.py` `CHANGE_REQUEST`, `CLAIMED_CHANGE` |

**Every run ends with an explicit outcome** (`success`, `budget_steps`,
`budget_cost`, `budget_tokens`, `deadline`, `loop_detected`, `invalid_output`,
`llm_unavailable`). No unhandled exceptions. The outcome mix becomes the SLI
([08](../08-sre-operations/LEARN.md)).

**Prompt vs code.** This lab measured it with real models
([eval history](../04-agent-evals/README.md#eval-history-real-runs-in-ci-qwen25-on-a-2-vcpu-github-runner-12-tasks--2-trials)):
adding four rules to the prompt made qwen2.5:1.5b *worse* (pass@1 0.33 → 0.29) and
made it claim "The payments-api deployment has been deleted." Moving the rule into
code took pass@1 to 0.71 and safety to 100%. **Deterministic rules go in code; the
prompt stays short**, especially for small models.

## 3. Walkthrough (no model needed)

```bash
cd 01-agent-runtime
python -m agentops.demo            # 7 scenarios through the real agent, tools and guards
```

Excerpt of the real output (trimmed):

```
### loop: 'Which runbook covers latency?'
  step 1: model -> {"action": "search_runbooks", "args": {"query": "latency"}}
    observation: Observation from search_runbooks: [{"runbook": "high-latency", ...}]
  step 2: model -> {"action": "search_runbooks", "args": {"query": "latency"}}
  step 3: model -> {"action": "search_runbooks", "args": {"query": "latency"}}
  => outcome=loop_detected steps=3 tools=['search_runbooks', 'search_runbooks'] cost=$0.000855

### provider-down: 'Is auth-service healthy?'
  step 1: model call failed (503 from provider, retryable=True)
  step 2: model call failed (503 from provider, retryable=True)
  step 3: model call failed (503 from provider, retryable=True)
  => outcome=llm_unavailable steps=1 tools=[] cost=$0.000000

### false-claim: 'payments-api looks broken, sort it out'
  step 1: model -> {"action": "final", "answer": "I have restarted payments-api, it is fine now."}
  => outcome=success ... guards={'blocked_false_change_claim': 1.0}
  => answer: I can only look things up; I can't make changes such as deleting, deploying, restarting...
```

Then read the code in this order (about 400 lines total):
1. [`agentops/resilience.py`](agentops/resilience.py): `Deadline`, `retry_call`, `CircuitBreaker`
2. [`agentops/tools.py`](agentops/tools.py): `ToolRegistry.validate` then `call` (timeout → breaker → retry)
3. [`agentops/agent.py`](agentops/agent.py): `Agent.run`. Notice the budget checks at the *top* of every step, and that every exit goes through `_finish`
4. [`agentops/telemetry.py`](agentops/telemetry.py): which labels are allowed on metrics, and why the run log has sizes but no text

With a real model: `ollama pull qwen2.5:1.5b`, then `python -m agentops "Is payments-api healthy?"`.

## 4. Exercises

```bash
cd ..                 # deloitte/
make check EX=01      # circuit breaker state machine
make check EX=02      # retry with full jitter and a deadline
make check EX=03      # loop detector + budget checks
```

Challenges:
1. Add a **side-effecting** tool (`create_ticket`) with `idempotent=False`. What must change
   in the guards? (Hint: `side_effects`, and should the change-request pre-check still refuse "create a ticket"?)
2. Add a `max_tool_errors` budget: stop after 3 failed tool calls in one run. Which outcome name, and
   should it count against the SLO?
3. Add a demo scenario `slow-tool` that shows the deadline cutting a slow tool short.

## 5. Break it

```bash
make break-it ID=agent-no-loop-detection
make break-it ID=agent-retries-everything
make break-it ID=tools-no-circuit-breaker
make break-it ID=agent-no-false-claim-guard
make break-it ID=agent-change-requests-reach-model
```

## 6. Check yourself

<details><summary>1. Why retry only idempotent tools?</summary>

A retry after a timeout may run the action twice: the first attempt may have succeeded and only the
response was lost. Re-reading a status twice is harmless; creating two tickets or two deployments is not.
</details>

<details><summary>2. A tool's breaker is open. What does the model see?</summary>

An observation `ERROR (circuit_open): ...`, returned immediately without calling the dependency. The model
can explain the lookup is unavailable or try another tool, and the dependency gets time to recover.
</details>

<details><summary>3. Why does the run log contain question_chars but not the question?</summary>

The log feeds drift detection and capacity analysis, which only need sizes and outcomes. Storing prompt
text would copy user data (possibly PII) into a system that doesn't need it. Capture text only where you
must, sampled and redacted (see Track A module 05).
</details>

<details><summary>4. Why is "refuse change requests" in code rather than in the prompt?</summary>

It's deterministic policy. In the real CI evals, putting it in the prompt *caused* the model to claim it had
deleted a deployment, and it also made the model worse at everything else. Code is cheaper (no model call),
consistent, and testable.
</details>

## 7. In the interview

* "What can go wrong with agents in production, and how did you bound it?" Walk the table in §2.
* "Tell me about a time a fix made things worse." Eval run 2: the prompt rules, the false deletion
  claim, and moving the policy into code. Have the numbers ready.
* "How do you know the agent is healthy?" The outcome mix as SLI, steps/cost histograms, tool-error
  rate, invalid-output rate, guard interventions.

## Go further
* Release It! (Nygard): circuit breakers, timeouts, bulkheads
* AWS Builders' Library: "Timeouts, retries, and backoff with jitter"
