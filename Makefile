.PHONY: install dev test coverage lint format check db-up db-down db-reset run docker-up docker-down fly-deploy fly-logs fly-ssh

install:
	uv sync --all-groups
	uv run pre-commit install

dev: db-up run

run:
	uv run streamlit run dashboard/app.py --server.port 8502

test:
	uv run pytest -v

coverage:
	uv run pytest --cov=rag --cov-report=term-missing --cov-report=html --cov-fail-under=70
	@echo "Rapport HTML disponible dans htmlcov/index.html"

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint test

db-up:
	docker compose up -d postgres

db-down:
	docker compose stop postgres

db-reset:
	docker compose down -v postgres
	docker compose up -d postgres

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

fly-deploy:
	flyctl deploy --image ghcr.io/seydinabane/rag-fintech:main

fly-logs:
	flyctl logs

fly-ssh:
	flyctl ssh console
