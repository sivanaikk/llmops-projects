"""Run a system-under-test over a dataset and aggregate the results."""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .scorers import Example, Output, Scorer

System = Callable[[str], Output]


def load_dataset(path: str | Path) -> list[Example]:
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            out.append(Example(d["id"], d["question"], d["must_include"], d.get("source"), tuple(d.get("tags", []))))
    return out


@dataclass
class Row:
    id: str
    question: str
    answer: str
    scores: dict[str, float]
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    error: str | None = None
    tags: tuple[str, ...] = ()


@dataclass
class RunResult:
    variant: str
    rows: list[Row]
    summary: dict = field(default_factory=dict)

    def save(self, out_dir: str | Path) -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with (out / f"{self.variant}.rows.jsonl").open("w") as f:
            for r in self.rows:
                f.write(json.dumps(asdict(r)) + "\n")
        path = out / f"{self.variant}.summary.json"
        path.write_text(json.dumps(self.summary, indent=2))
        return path

    @classmethod
    def load(cls, out_dir: str | Path, variant: str) -> RunResult:
        out = Path(out_dir)
        rows = [Row(**{**json.loads(line), "tags": tuple(json.loads(line).get("tags", []))})
                for line in (out / f"{variant}.rows.jsonl").read_text().splitlines() if line]
        return cls(variant, rows, json.loads((out / f"{variant}.summary.json").read_text()))


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def summarize(variant: str, rows: list[Row]) -> dict:
    names = sorted({k for r in rows for k in r.scores})
    ok = [r for r in rows if not r.error]
    lat = [r.latency_s for r in ok]
    by_tag: dict[str, list[float]] = {}
    for r in rows:
        for t in r.tags:
            by_tag.setdefault(t, []).append(r.scores.get("fact_recall", 0.0))
    return {
        "variant": variant,
        "n": len(rows),
        "errors": len(rows) - len(ok),
        "scores": {n: round(statistics.fmean(r.scores.get(n, 0.0) for r in rows), 4) for n in names},
        "fact_recall_by_tag": {t: round(statistics.fmean(v), 4) for t, v in sorted(by_tag.items())},
        "latency_p50_s": round(_pct(lat, 0.5), 3),
        "latency_p95_s": round(_pct(lat, 0.95), 3),
        "avg_prompt_tokens": round(statistics.fmean(r.prompt_tokens for r in ok), 1) if ok else 0,
        "avg_completion_tokens": round(statistics.fmean(r.completion_tokens for r in ok), 1) if ok else 0,
    }


def run(variant: str, system: System, dataset: list[Example], scorers: list[Scorer], concurrency: int = 4) -> RunResult:
    def one(ex: Example) -> Row:
        try:
            out = system(ex.question)
        except Exception as e:  # a failed call scores 0 and is counted, not hidden
            out = Output("", [], [], error=f"{type(e).__name__}: {e}")
        scores = {s.name: (0.0 if out.error else float(s(ex, out))) for s in scorers}
        return Row(ex.id, ex.question, out.answer, scores, out.latency_s, out.prompt_tokens, out.completion_tokens,
                   out.error, ex.tags)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = list(pool.map(one, dataset))
    return RunResult(variant, rows, summarize(variant, rows))
