# 06 · Evals and experimentation infra (`evalkit`)

> **Learning this?** Start with the lesson: [LEARN.md](LEARN.md) (concepts, walkthrough, exercises, break-it labs, self-check).

> JD: *"The shared harnesses, datasets, and scoring plumbing product teams use
> to know whether a prompt or model change actually made things better"* and
> *"LLM-as-judge scoring in a real workflow, not a demo."*

```
datasets/account_qa.jsonl      16 questions: lookups, numbers, people, compliance,
                               reasoning, and 2 unanswerable (must abstain)
variants/*.yaml                a variant = model + prompt version + retrieval params
evalkit/scorers.py             fact_recall, retrieval_hit, abstention_correct, concise,
                               judge_faithfulness (LLM-as-judge via the `judge` model group)
evalkit/runner.py              runs the system under test, aggregates scores, p50/p95, tokens
evalkit/compare.py             paired bootstrap CI per metric → regression gate
```

## The workflow

```bash
make evals          # run baseline, candidate-prompt-v2 and candidate-tiny on the real models
make eval-compare   # markdown report; exit 1 if the candidate regresses
```

In CI ([`.gitlab-ci.yml`](../.gitlab-ci.yml) `eval-gate`), any MR touching
prompts, the RAG app or the gateway config runs this and attaches the report.

## Decisions baked in

* **Separate retrieval from generation.** `retrieval_hit` tells you whether a
  bad answer is the retriever's fault or the model's.
* **Unanswerable questions in the set.** Without them a model that confidently
  makes things up scores well.
* **Statistical gate, not "the mean went down."** With 16-200 examples, a few
  points of difference is noise. The gate only fails when the 90% bootstrap CI
  of the per-example difference sits entirely below the tolerance.
* **The judge is checked too.** Unparseable judge output scores 0 and is
  counted (`judge_parse_failures` in the summary, plus a warning), so a broken
  judge can't pass quietly. The judge goes through the gateway on its own
  `eval-judge` feature tag, so eval spend shows up in showback.
* **Evals bypass caches** (`use_cache=False`); a cached answer isn't a measurement.

## Experiments the variants set up

| Variant | Question it answers |
|---|---|
| `candidate-prompt-v2` | Does a stricter grounding prompt (abstain + cite) improve abstention without hurting fact recall? The longer system prompt costs more input tokens per call; the report shows how many. |
| `candidate-tiny` | Can the 360M model replace the 0.5B one for this feature, and what does it cost in quality? |

Results land in `results/` (git-ignored). Run them yourself; the numbers depend on your hardware and model versions.
