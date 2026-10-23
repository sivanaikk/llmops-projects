"""Where eval results go.

* MLflow   - experiment tracking: one run per variant, params + metrics + the
             full result as an artifact, so "which prompt/model won" has a history.
* Langfuse - one trace per trial with scores, for teams already looking at
             production traces there (optional; needs LANGFUSE_* env vars).
* JSON     - always written locally; CI artifacts and the gate read these.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .runner import EvalResult


class Tracker(Protocol):
    def log(self, result: EvalResult, params: dict) -> str: ...


class JsonTracker:
    def __init__(self, out_dir: str | Path):
        self.out = Path(out_dir)

    def log(self, result: EvalResult, params: dict) -> str:
        self.out.mkdir(parents=True, exist_ok=True)
        path = self.out / f"{result.variant}.json"
        path.write_text(json.dumps({"params": params, **result.to_dict()}, indent=2))
        return str(path)


class MLflowTracker:
    def __init__(self, tracking_uri: str | None = None, experiment: str = "incident-desk-agent-evals"):
        import mlflow  # optional dependency

        self.mlflow = mlflow
        if tracking_uri or os.getenv("MLFLOW_TRACKING_URI"):
            mlflow.set_tracking_uri(tracking_uri or os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(experiment)

    def log(self, result: EvalResult, params: dict) -> str:
        mlflow, s = self.mlflow, result.summary
        with mlflow.start_run(run_name=result.variant) as run:
            mlflow.log_params({k: v for k, v in params.items() if isinstance(v, (str, int, float, bool))})
            mlflow.log_metrics({k: float(v) for k, v in s.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
            mlflow.log_metrics({f"pass_rate.{tag}": v for tag, v in s["pass_rate_by_tag"].items()})
            mlflow.set_tags({"suite": params.get("suite", ""), "flaky_tasks": ",".join(s["flaky_tasks"])[:250]})
            mlflow.log_dict(result.to_dict(), "eval_result.json")
            return run.info.run_id


class LangfuseTracker:
    def __init__(self):
        from langfuse import Langfuse  # optional dependency; reads LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST

        self.lf = Langfuse()

    def log(self, result: EvalResult, params: dict) -> str:
        for t in result.trials:
            trace = self.lf.trace(name=f"eval:{t.task_id}", tags=[result.variant, *t.tags],
                                  metadata={"variant": result.variant, "trial": t.trial, "tools": t.tools},
                                  output=t.answer)
            trace.score(name="passed", value=1.0 if t.passed else 0.0)
            trace.score(name="steps", value=float(t.steps))
        self.lf.flush()
        return f"{len(result.trials)} traces"
