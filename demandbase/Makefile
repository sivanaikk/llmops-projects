# AI Runtime Services lab. `make help` for targets.
SHELL := /bin/bash
PY ?= python3
export PYTHONPATH := 02-guardrails:03-semantic-cache:04-cost-control:05-llm-observability:06-evals-harness:07-account-rag-app

.PHONY: help install test e2e lint up down bootstrap smoke evals eval-compare showback cache-bench gitops-rules validate gameday load

help:          ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:       ## install dev dependencies
	$(PY) -m pip install -r requirements-dev.txt

test:          ## unit tests for every project (no models needed)
	$(PY) -m pytest

e2e:           ## real LiteLLM proxy + plugins against mock providers (no models needed)
	$(PY) 01-llm-gateway/e2e/run_e2e.py

lint:          ## ruff
	$(PY) -m ruff check .

up:            ## start the full stack and pull the small models (~2 GB)
	@test -f .env || cp .env.example .env
	docker compose up -d --build
	docker compose logs -f model-puller

down:          ## stop the stack (keeps model volumes)
	docker compose down

bootstrap:     ## create teams + virtual keys with budgets
	set -a; source .env; set +a; $(PY) 01-llm-gateway/scripts/bootstrap_teams.py

smoke:         ## end-to-end checks against the running gateway
	set -a; source .env; set +a; $(PY) 01-llm-gateway/scripts/smoke_test.py

evals:         ## run baseline + candidates through the real models (judge included)
	set -a; source .env; set +a; \
	for v in baseline candidate-prompt-v2 candidate-tiny; do \
	  $(PY) -m evalkit run 06-evals-harness/variants/$$v.yaml --judge || exit 1; done

eval-compare:  ## regression gate: candidate-prompt-v2 vs baseline (exit 1 on regression)
	$(PY) -m evalkit compare baseline candidate-prompt-v2 --report 06-evals-harness/results/report.md

showback:      ## cost showback + budget alerts (synthetic data if no stack: make showback DEMO=1)
	cd 04-cost-control && $(PY) -m costwatch.report $(if $(DEMO),--demo,)

cache-bench:   ## semantic cache threshold sweep (GATEWAY=1 to use all-minilm via the gateway)
	$(PY) 03-semantic-cache/bench/benchmark.py $(if $(GATEWAY),--gateway,)

gitops-rules:  ## regenerate the PrometheusRule CR from the alert rules
	$(PY) 08-platform-infra/scripts/gen_prometheus_rule.py

validate:      ## promtool + kustomize + terraform validation (tools must be on PATH)
	promtool check rules 05-llm-observability/prometheus/rules/slo-alerts.yml
	promtool test rules 05-llm-observability/prometheus/rules/slo-alerts.test.yml
	$(PY) 08-platform-infra/scripts/gen_prometheus_rule.py --check
	kustomize build 08-platform-infra/gitops/apps/dev | kubeconform -strict -ignore-missing-schemas -summary
	kustomize build 08-platform-infra/gitops/infrastructure | kubeconform -strict -ignore-missing-schemas -summary
	cd 08-platform-infra/terraform && terraform init -backend=false -input=false >/dev/null && terraform validate && terraform fmt -check

gameday:       ## SCENARIO=primary-outage|secondary-outage|slow-provider|redis-outage
	set -a; source .env; set +a; $(PY) 09-sre/tools/game_day.py --scenario $(or $(SCENARIO),primary-outage)

load:          ## RPS=5 DURATION=60 load test against the gateway
	set -a; source .env; set +a; $(PY) 09-sre/tools/loadgen.py --rps $(or $(RPS),2) --duration $(or $(DURATION),30)
