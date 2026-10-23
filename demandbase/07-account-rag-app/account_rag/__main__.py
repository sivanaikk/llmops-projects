"""python -m account_rag "Who is the economic buyer at Northwind Robotics?" """

import sys

from llmobs import LLMTracer

from .app import AccountAssistant
from .gateway import GatewayClient

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Summarize Northwind Robotics' intent and buying group."
    a = AccountAssistant(GatewayClient(), tracer=LLMTracer(capture_ratio=0)).answer(question)
    print(a.text)
    print(f"\nsources: {', '.join(a.sources)} | {a.latency_s:.2f}s | usage: {a.usage}")
