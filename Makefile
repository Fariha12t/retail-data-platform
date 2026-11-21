.PHONY: help install up down api init demo run test test-integration lint dbt-docs dashboard clean
PY ?= python
export PYTHONPATH := $(CURDIR)/src
export DBT_PROFILES_DIR := $(CURDIR)/dbt

help:            ## show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

install:         ## install dependencies (use a virtualenv)
	pip install -r requirements-dev.txt -r requirements-dashboard.txt

up:              ## start Postgres, MinIO and the mock API in Docker
	docker compose up -d postgres minio minio-init mock-api

down:            ## stop all containers
	docker compose down

api:             ## run the mock marketing API locally (needed if you don't use docker for it)
	$(PY) -m retail_pipeline.mock_api

init:            ## create schemas and audit tables
	$(PY) -m retail_pipeline.cli init-db

demo:            ## seed 60 days, initial load, then 3 incremental days (needs `make up`)
	scripts/demo.sh

run:             ## run the daily pipeline for one date: make run DATE=2026-01-31
	scripts/run_pipeline.sh $(DATE)

test:            ## unit tests (no services needed)
	pytest -q

test-integration: ## DESTRUCTIVE end-to-end test: use a throw-away database
	ALLOW_DESTRUCTIVE_TESTS=1 pytest -q -m integration

lint:
	ruff check .

dbt-docs:        ## build and serve dbt docs (lineage graph) on :8081
	cd dbt && dbt docs generate && dbt docs serve --port 8081

dashboard:       ## Streamlit dashboard on :8501
	streamlit run dashboard/app.py

clean:
	rm -rf data/lake data/landing/*.csv data/landing/.inventory_state.json reports/* dbt/target dbt/logs
