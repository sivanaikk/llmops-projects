import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentops import LLMError, OpenAICompatClient, ScriptedLLM


def test_openai_client_parses_usage_and_classifies_errors():
    def handler(req: httpx.Request):
        body = json.loads(req.content)
        assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
        return httpx.Response(200, json={"model": "qwen2.5:1.5b", "usage": {"prompt_tokens": 12, "completion_tokens": 5},
                                         "choices": [{"message": {"content": '{"action":"final","answer":"x"}'}}]})

    c = OpenAICompatClient(model="qwen2.5:1.5b", base_url="http://llm/v1")
    c.http = httpx.Client(transport=httpx.MockTransport(handler))
    r = c.complete([{"role": "user", "content": "hi"}], timeout=5, max_tokens=50)
    assert r.prompt_tokens == 12 and r.completion_tokens == 5

    for status, retryable in [(429, True), (503, True), (400, False)]:
        c.http = httpx.Client(transport=httpx.MockTransport(lambda req, s=status: httpx.Response(s, text="nope")))
        with pytest.raises(LLMError) as e:
            c.complete([], timeout=5, max_tokens=5)
        assert e.value.retryable is retryable

    def timeout(req):
        raise httpx.ReadTimeout("slow", request=req)

    c.http = httpx.Client(transport=httpx.MockTransport(timeout))
    with pytest.raises(LLMError) as e:
        c.complete([], timeout=1, max_tokens=5)
    assert e.value.retryable


def test_http_service(monkeypatch):
    from agentops import server

    monkeypatch.setattr(server.agent, "llm", ScriptedLLM([
        json.dumps({"action": "get_error_budget", "args": {"service": "auth-service"}}),
        json.dumps({"action": "final", "answer": "gate open"}),
    ]))
    client = TestClient(server.app)
    r = client.post("/run", json={"question": "Can we ship to auth-service?"})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "success" and body["tools"] == ["get_error_budget"]
    assert client.post("/run", json={"question": ""}).status_code == 422
    metrics = client.get("/metrics").text
    assert 'agent_runs_total{agent="incident-desk",outcome="success"} 1.0' in metrics
    assert client.get("/readyz").status_code == 503  # no model backend in tests -> not ready
