# Learn: evaluating agents (and trusting the numbers)

**You'll be able to:** write trajectory-level eval tasks; explain pass@1 vs
pass^k and when each matters; find eval bugs vs model bugs from per-trial
results; track experiments in MLflow; gate promotions on evals.
**Time:** ~2 h · **Needs:** Python (Ollama for real-model runs, or let CI run them)

---

## 1. The problem

"The answer contains the right word" isn't enough for an agent. It can be right
by luck (it guessed without looking anything up), right one time in three, or right
while claiming it did something it can't do. And a single run tells you very
little, because agents aren't deterministic.

## 2. Concepts

**Trajectory checks.** Each task in [`suites/incident-desk.yaml`](suites/incident-desk.yaml)
checks *how* the agent answered, not just what it said:

```yaml
- id: multi-hop
  question: Is payments-api degraded, and if so, does it still have enough error budget to ship a feature?
  expect: {answer_contains: [degraded], answer_contains_any: [open, "18%", ...],
           tools_required: [get_service_status, get_error_budget]}
```

Named boolean checks (`tools_required`, `answer_not_contains`, `max_tool_calls`,
`outcome_success`, ...) mean a failure says exactly what broke.

**pass@1 vs pass^k** (k trials per task):

```
task       trials        pass@1 contribution   pass^k
status     ✓ ✓ ✓         3/3                   ✓
budget     ✓ ✗ ✓         2/3                   ✗   <- flaky
math       ✗ ✗ ✗         0/3                   ✗
pass@1 = 5/9 = 0.56          pass^k = 1/3 = 0.33
```

pass@1 is what one user sees on average. pass^k is what an SLO feels: "does it work *every* time?"

**Eval bugs vs model bugs.** The first real run ([README](README.md#eval-history-real-runs-in-ci-qwen25-on-a-2-vcpu-github-runner-12-tasks--2-trials))
had 5 of 16 baseline failures that were *the eval's* fault ("Runbook: high latency"
failed a check for `high-latency`). Always read the failing trials before trusting a score,
and **don't re-tune checks after seeing results** to make a candidate pass.

**Promotion gate** ([`agentevals/gate.py`](agentevals/gate.py)): no drop in pass^k, at most a
5-point drop in pass@1, at most 30% more cost, at most +1 average step, and an absolute pass^k floor.

## 3. Walkthrough

```bash
cd ..  # deloitte/
pytest 04-agent-evals -q          # a scripted "oracle" agent scores 100%, a lazy one fails tools checks
```

Read [`tests/test_agentevals.py`](tests/test_agentevals.py) `oracle` and `lazy`: two fake agents
that let you test the *harness* without a model. That's how you check that your evals can fail.

Real models: CI runs this on every push whose commit message contains `[run-evals]`,
and nightly. Locally:

```bash
ollama pull qwen2.5:1.5b && ollama pull qwen2.5:0.5b
LLM_BASE_URL=http://localhost:11434/v1 PYTHONPATH=01-agent-runtime:04-agent-evals \
  python -m agentevals run 04-agent-evals/variants/baseline.yaml --trials 2
python -m agentevals compare baseline candidate-0.5b
```

Real results from CI (12 tasks × 2 trials, qwen2.5 on a 2-vCPU runner):

| | pass@1 | pass^k | clean outcomes |
|---|---|---|---|
| qwen2.5:1.5b (run 3) | 0.71 | 0.67 | 96% |
| qwen2.5:0.5b (run 3) | 0.08 | 0.08 | 21% |

## 4. Exercises

```bash
make check EX=05     # pass@1, pass^k, flaky tasks, the unbiased pass@k estimator
```

Challenges:
1. Add 3 tasks: one that needs `calculator` with a unit conversion, one ambiguous question where the
   right answer is to ask for clarification, and one prompt-injection attempt hidden in a question.
   Which checks express "asked for clarification"?
2. Run `candidate-tight-steps` against the baseline. Predict first which tags drop.
3. Add an LLM-as-judge scorer (see Track A [06-evals-harness](../../demandbase/06-evals-harness/LEARN.md))
   for answer faithfulness to the tool observations.

## 5. Break it

```bash
make break-it ID=evals-pass-hat-k-is-average
make break-it ID=evals-ignore-trajectory
```

## 6. Check yourself

<details><summary>1. pass@1 went up and pass^k went down. Ship it?</summary>

No. On average it's better, but fewer tasks work reliably. Users will see it fail on things that used to
work every time. Look at the `flaky_tasks` list; the gate blocks any pass^k drop.
</details>

<details><summary>2. Why run each task more than once?</summary>

Even at temperature 0, outputs vary (batching, retries, provider changes). One run gives a coin-flip
estimate. k ≥ 2 exposes flakiness; the pass@k estimator tells you the chance at least one of k attempts passes.
</details>

<details><summary>3. An eval check rejects a correct answer. What do you do?</summary>

Fix the check, but decide the rule *before* looking at candidate results, and record it. Changing
checks after seeing a candidate's failures until it passes is how eval suites stop meaning anything.
</details>

<details><summary>4. Why does `build_agent` create a fresh ToolRegistry per trial?</summary>

Circuit breakers keep state. If one trial opened a breaker, the next trial would start with a broken tool
and fail for reasons unrelated to the change being evaluated.
</details>

## 7. In the interview

* "How do you know a prompt change made things better?" Trajectory evals, k trials, pass^k, read the
  failing trials, then the gate. Cite the three CI runs.
* "Have you used LLM-as-judge?" Where it helps (faithfulness), where it doesn't (exact facts), and that
  you track judge parse failures so a broken judge can't pass silently.

## Go further
* Chen et al. 2021 (Codex paper): the unbiased pass@k estimator
* Yao et al. 2024, τ-bench: the benchmark that introduced pass^k for tool-using agents
