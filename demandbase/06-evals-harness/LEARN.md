# Learn: evals that can tell a regression from noise

**You'll be able to:** design an eval dataset (including questions that must not be
answered); separate retrieval failures from generation failures; use LLM-as-judge
carefully; gate a prompt change with a paired bootstrap instead of eyeballing averages.
**Time:** ~2 h · **Needs:** Python (gateway + models for real runs)

---

## 1. The problem

"The new prompt scored 0.81 vs 0.84, ship it or not?" With 16 examples, that 3-point
gap is mostly noise. And a dataset with only answerable questions rewards a model
that confidently makes things up.

## 2. Concepts

**Dataset design** ([`datasets/account_qa.jsonl`](datasets/account_qa.jsonl)): lookups, numbers, people,
compliance, reasoning, and **unanswerable** questions ("Who is the CFO of Contoso Health?": not in the notes)
where the correct answer is "I don't know".

**Scorers** ([`evalkit/scorers.py`](evalkit/scorers.py)):

| Scorer | Catches |
|---|---|
| `fact_recall` | missing facts (and, on unanswerable questions, made-up answers) |
| `retrieval_hit` | the retriever didn't find the right chunk: a retrieval bug, not a generation bug |
| `abstention_correct` | hallucinating on unanswerable / refusing answerable |
| `judge_faithfulness` | claims not supported by the context (LLM-as-judge; parse failures counted) |

**Paired bootstrap** ([`evalkit/compare.py`](evalkit/compare.py)): take the per-example differences
(candidate − baseline), resample them 2000 times, and take the 90% interval of the mean.
**Regression only if the whole interval is below −tolerance**, i.e. we're confident it got worse.

Real numbers (16 examples, tolerance 0.05; from the exercise's reference solution):
```
2 lost, 1 gained   mean −0.06, 90% CI [−0.25, +0.13]  →  could be noise: PASS
6 lost             mean −0.38, 90% CI [−0.56, −0.19]  →  confidently worse: FAIL
```

## 3. Walkthrough

```bash
pytest 06-evals-harness -q
```

Read `test_compare_flags_regression` and `test_identical_runs_pass_gate` in
[`tests/test_evalkit.py`](tests/test_evalkit.py): an oracle system scores 1.0, a broken one is flagged,
and identical runs pass. Testing the harness with known-good and known-bad systems is how you trust it.

With the stack: `make evals && make eval-compare` writes a markdown report suitable for an MR comment.

## 4. Exercises

```bash
make check EX=05     # bootstrap CI and the regression decision
```

Challenges:
1. Run the evals with and without `--judge` on real models. Check `judge_parse_failures`. If the judge
   (qwen2.5:1.5b) is unreliable, what would you do: bigger judge, stricter output format, or drop it?
2. Calibrate the judge: hand-label 10 answers as faithful or not and measure agreement.
3. Add 5 adversarial examples where the context contradicts common knowledge. Does the model trust the context?

## 5. Break it

```bash
make break-it ID=evals-unanswerable-scored-as-pass   # this one found a real test gap
make break-it ID=evals-gate-never-fails
```

When the break-it catalogue was first run, `evals-unanswerable-scored-as-pass` **survived**: no test checked
that a made-up answer to an unanswerable question scores 0. The missing assertion was added. That's
mutation testing doing its job.

## 6. Check yourself

<details><summary>1. retrieval_hit is 0.8 and fact_recall is 0.3. Where's the problem?</summary>

Generation: the right chunk was retrieved most of the time, but the model didn't use it. Look at the prompt
and the model. If retrieval_hit were low, fix chunking and the embedder first.
</details>

<details><summary>2. Why a paired bootstrap instead of comparing two averages?</summary>

Pairing removes example difficulty (both systems saw the same questions), and the bootstrap gives an
uncertainty range without assuming a distribution, which matters with few examples.
</details>

<details><summary>3. When is LLM-as-judge a bad idea?</summary>

For exact facts and numbers (string checks are cheaper and deterministic), and whenever the judge
is no better than the model being judged. Always calibrate it against human labels and track parse failures.
</details>

## 7. In the interview

* "How do you know a prompt change is better?" Dataset with unanswerables, per-scorer results, a paired
  bootstrap gate, a report on the MR.

## Go further
* Efron & Tibshirani, *An Introduction to the Bootstrap*
* Zheng et al. 2023, "Judging LLM-as-a-Judge" (MT-Bench)
