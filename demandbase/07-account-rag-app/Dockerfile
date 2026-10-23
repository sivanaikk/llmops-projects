# Build context is the demandbase/ directory (see docker-compose.yml).
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]>=0.29" "httpx>=0.27" "pyyaml>=6.0" \
    "opentelemetry-sdk>=1.25" "opentelemetry-exporter-otlp-proto-http>=1.25"

COPY 02-guardrails/guardkit ./guardkit
COPY 03-semantic-cache/semcache ./semcache
COPY 05-llm-observability/llmobs ./llmobs
COPY 07-account-rag-app/account_rag ./account_rag
COPY 07-account-rag-app/data ./data

# index.py resolves data relative to the package's parent dir: /app/data
ENV PYTHONPATH=/app
EXPOSE 8080
USER nobody
CMD ["uvicorn", "account_rag.server:app", "--host", "0.0.0.0", "--port", "8080"]
