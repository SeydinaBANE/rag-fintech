.PHONY: install dev test lint format check db-up db-down db-reset run docker-up docker-down

install:
	uv sync --all-groups
	uv run pre-commit install

dev: db-up run

run:
	uv run streamlit run dashboard/app.py --server.port 8502

test:
	uv run pytest -v

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
