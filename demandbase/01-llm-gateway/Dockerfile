# LiteLLM proxy + the runtime's plugins (guardrails, cost, metrics).
# Build context is the demandbase/ directory (see docker-compose.yml).
# In production pin the base image by digest and let Renovate bump it.
FROM ghcr.io/berriai/litellm:main-stable

WORKDIR /app/plugins
COPY 01-llm-gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY 01-llm-gateway ./01-llm-gateway
COPY 02-guardrails/guardkit ./02-guardrails/guardkit
COPY 02-guardrails/policies.yaml ./02-guardrails/policies.yaml
COPY 04-cost-control/costwatch ./04-cost-control/costwatch
COPY 05-llm-observability/llmobs ./05-llm-observability/llmobs

ENV PYTHONPATH=/app/plugins/01-llm-gateway:/app/plugins/02-guardrails:/app/plugins/04-cost-control:/app/plugins/05-llm-observability
EXPOSE 4000 9464
