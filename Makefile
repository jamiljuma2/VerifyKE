# VerifyKE developer entry points.
#
# Everything below works with a local virtualenv (`.venv`) and a local Node
# toolchain. Docker equivalents are noted where they exist.

SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
API_DIR := apps/api

.DEFAULT_GOAL := help
.PHONY: help venv install env secrets api web test test-api lint format typecheck \
        migrate migration up down logs ps shell psql redis-cli clean check

help: ## Show this help
@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the Python virtualenv
python3.12 -m venv $(VENV) 2>/dev/null || python3 -m venv $(VENV)
$(PIP) install --upgrade pip setuptools wheel
@echo "Virtualenv ready at $(VENV)"

install: venv ## Install API dependencies (editable, with dev extras)
$(PIP) install -e "$(API_DIR)[dev]"

env: ## Create .env from the template (never overwrites an existing .env)
@if [ -f .env ]; then echo ".env already exists - leaving it untouched"; \
else cp .env.example .env && echo "Created .env - fill in the secrets"; fi

secrets: ## Generate strong development secrets (SECRET_KEY + MASTER_KEY)
@$(PY) scripts/dev/generate_secrets.py

api: ## Run the API with autoreload on :8000
$(VENV)/bin/uvicorn verifyke.main:app --reload --reload-dir $(API_DIR)/verifyke \
--app-dir $(API_DIR) --host 0.0.0.0 --port 8000

web: ## Run the Next.js app on :3000
npm run dev --workspace @verifyke/web

test: ## Run the whole test suite
$(VENV)/bin/pytest -c $(API_DIR)/pyproject.toml $(API_DIR)/tests

check: lint typecheck test ## Everything CI runs for a pull request

lint: ## Ruff (lint + format check) for Python, ESLint for TypeScript
$(VENV)/bin/ruff check $(API_DIR)
$(VENV)/bin/ruff format --check $(API_DIR)
npm run lint --if-present

format: ## Auto-format Python and TypeScript
$(VENV)/bin/ruff format $(API_DIR)
$(VENV)/bin/ruff check --fix $(API_DIR)
npm run format --if-present

typecheck: ## Mypy for Python, tsc for TypeScript
$(VENV)/bin/mypy --config-file $(API_DIR)/pyproject.toml $(API_DIR)/verifyke
npm run typecheck --if-present

migrate: ## Apply all database migrations
cd $(API_DIR) && ../../$(VENV)/bin/alembic upgrade head

migration: ## Create a migration: make migration m="add certificates table"
@test -n "$(m)" || (echo 'usage: make migration m="description"'; exit 1)
cd $(API_DIR) && ../../$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

up: ## Start the Docker stack
docker compose up -d

down: ## Stop the Docker stack
docker compose down

logs: ## Tail Docker logs
docker compose logs -f --tail=100

ps: ## Show container status
docker compose ps

shell: ## Open a shell in the API container
docker compose exec api /bin/sh

psql: ## Open psql against the Compose database
docker compose exec postgres psql -U $${POSTGRES_USER:-verifyke} -d $${POSTGRES_DB:-verifyke}

redis-cli: ## Open redis-cli against the Compose Redis
docker compose exec redis redis-cli

clean: ## Remove caches and build output (keeps .venv and node_modules)
rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__ apps/web/.next \
htmlcov .coverage .coverage.*
@echo "Caches removed"
