# Applied AI SRE lab. `make help` lists targets.
SHELL := /bin/bash
PY ?= python3
export PYTHONPATH := 01-agent-runtime:03-drift-cost-sentinel:04-agent-evals:05-resilience
export MLFLOW_DISABLE_AGENT_HINT := 1

.PHONY: help install test go-test lint validate up down ask evals eval-compare sentinel-demo load chaos capacity rules gate

help:          ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:       ## Python dev dependencies
	$(PY) -m pip install -r requirements-dev.txt

test:          ## all Python tests + Go tests (no model needed)
	$(PY) -m pytest
	cd 02-error-budget-gate && go test ./...

lint:          ## ruff + gofmt + go vet
	$(PY) -m ruff check .
	cd 02-error-budget-gate && test -z "$$(gofmt -l .)" && go vet ./...

rules:         ## regenerate Prometheus SLO rules from the SLO specs
	cd 02-error-budget-gate && go run ./cmd/budgetgate rules --slos slos --out ../observability/prometheus/rules/slo-generated.yml

validate:      ## promtool, helm+kubeconform, terraform, k6 (tools on PATH)
	cd observability/prometheus/rules && promtool check rules agent-alerts.yml slo-generated.yml && promtool test rules alerts.test.yml
	helm lint 06-platform-azure/helm/agent-runtime
	helm template rel 06-platform-azure/helm/agent-runtime | kubeconform -strict -summary -ignore-missing-schemas
	cd 06-platform-azure/terraform && terraform init -backend=false -input=false >/dev/null && terraform validate && terraform fmt -check
	k6 inspect 05-resilience/k6/agent-load.js >/dev/null && echo "k6 script ok"

up:            ## start the stack and pull qwen2.5:1.5b + 0.5b (~1.4 GB)
	docker compose up -d --build
	docker compose logs -f model-puller

down:          ## stop the stack
	docker compose down

ask:           ## Q="..." ask the running agent
	@curl -s localhost:8000/run -H 'content-type: application/json' -d "{\"question\": \"$(or $(Q),Is payments-api healthy?)\"}" | $(PY) -m json.tool

evals:         ## agent evals on the real models (needs `make up`), logged to MLflow
	LLM_BASE_URL=http://localhost:11434/v1 MLFLOW_TRACKING_URI=http://localhost:5000 \
	  sh -c 'for v in baseline candidate-0.5b candidate-tight-steps; do $(PY) -m agentevals run 04-agent-evals/variants/$$v.yaml --trials 3 --tracker mlflow || exit 1; done'

eval-compare:  ## promotion gate: candidate-0.5b vs baseline
	$(PY) -m agentevals compare baseline candidate-0.5b --report eval-report.md

sentinel-demo: ## drift/cost detectors on synthetic scenarios
	for s in normal prompt_drift model_regression cost_spike tool_outage; do echo "== $$s"; $(PY) -m sentinel.monitor --demo $$s; done; true

load:          ## RPS=1 k6 steady + spike against the agent
	k6 run -e RPS=$(or $(RPS),1) --summary-export=summary.json 05-resilience/k6/agent-load.js

capacity:      ## TARGET_RPS=5 capacity plan from the last k6 run
	$(PY) -m resilience.capacity --k6-summary summary.json --target-rps $(or $(TARGET_RPS),5)

chaos:         ## Toxiproxy experiments against the running stack
	$(PY) -m resilience.chaos 05-resilience/experiments/*.yaml --report chaos-report.md

gate:          ## error-budget gate against local Prometheus
	cd 02-error-budget-gate && go run ./cmd/budgetgate check --slo slos/agent-runtime.yaml --prometheus http://localhost:9090
