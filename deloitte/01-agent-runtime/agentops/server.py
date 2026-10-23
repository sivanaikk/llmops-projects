"""HTTP service for the agent.

    uvicorn agentops.server:app --port 8000

/readyz checks the model backend, so Kubernetes stops sending traffic to a pod
whose model path is broken instead of letting every request time out.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from .agent import Agent, AgentConfig
from .builtin_tools import default_tools
from .llm import OpenAICompatClient
from .telemetry import Telemetry
from .tools import ToolRegistry


def _setup_tracing() -> None:
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "agent-runtime")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


_setup_tracing()
telemetry = Telemetry(run_log=os.getenv("AGENT_RUN_LOG"))
llm = OpenAICompatClient()
config = AgentConfig(
    max_steps=int(os.getenv("AGENT_MAX_STEPS", "6")),
    max_cost_usd=float(os.getenv("AGENT_MAX_COST_USD", "0.01")),
    deadline_s=float(os.getenv("AGENT_DEADLINE_S", "60")),
)
agent = Agent(llm, ToolRegistry(default_tools()), config, telemetry)
app = FastAPI(title="agent-runtime")


class RunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.post("/run")
def run(req: RunRequest):
    r = agent.run(req.question)
    return {"run_id": r.run_id, "outcome": r.outcome, "answer": r.answer, "steps": r.steps,
            "tools": [c.tool for c in r.tool_calls], "cost_usd": r.cost_usd, "duration_s": round(r.duration_s, 3)}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz(response: Response):
    try:
        httpx.get(f"{llm.base_url}/models", timeout=2).raise_for_status()
        return {"ready": True}
    except httpx.HTTPError as e:
        response.status_code = 503
        return {"ready": False, "reason": str(e)[:200]}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(telemetry.registry), media_type=CONTENT_TYPE_LATEST)
