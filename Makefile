# Alberta School Capacity & Utilization Planning Platform
# Needs: Docker, uv, GNU make (Windows: `winget install ezwinports.make`, or use Git Bash).

UV  ?= uv
BE  := cd backend &&

.PHONY: help setup data audit sample migrate pipeline pipeline-sample verify db-up db-down dev test lint format clean

help:          ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup:         ## Install backend dependencies and copy .env
	@test -f .env || cp .env.example .env
	$(BE) $(UV) sync

data:          ## Download all public source files into data/raw/
	$(BE) $(UV) run abcap download

audit:         ## Recompute the source facts behind docs/source_mapping.md
	$(BE) $(UV) run abcap audit --out ../docs/source_audit.json

db-up:         ## Start PostgreSQL + PostGIS
	docker compose up -d db

db-down:       ## Stop all containers
	docker compose down

sample:        ## Rebuild data/sample/ (small real subset) from data/raw/
	$(BE) $(UV) run abcap make-sample

migrate:       ## Apply database migrations (needs `make db-up`)
	$(BE) $(UV) run abcap migrate

pipeline: migrate  ## Load data/raw/ into PostgreSQL and verify row counts (dbt, checks, forecast follow)
	$(BE) $(UV) run abcap run

pipeline-sample: migrate  ## Same as pipeline, on the committed sample (no download needed)
	$(BE) $(UV) run abcap run --source sample

verify:        ## Compare source-file row counts with the raw tables
	$(BE) $(UV) run abcap verify

dev:           ## Run database + API (frontend joins in Phase 6)
	docker compose up --build

test:          ## Run backend tests (database tests need `make db-up`)
	$(BE) $(UV) run pytest -q

lint:          ## Lint and format-check backend code
	$(BE) $(UV) run ruff check . && $(UV) run ruff format --check .

format:        ## Auto-format backend code
	$(BE) $(UV) run ruff check --fix . && $(UV) run ruff format .

clean:         ## Remove containers, the database volume and downloaded raw files
	docker compose down -v
	find data/raw -mindepth 1 ! -name .gitkeep -delete
