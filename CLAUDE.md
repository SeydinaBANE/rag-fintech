# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies + pre-commit hooks
make install           # uv sync --all-groups && pre-commit install

# Run the app (local dev — requires postgres-fintech container on port 5433)
make run               # uv run streamlit run dashboard/app.py --server.port 8502
# Open http://localhost:8502

# Run tests (no DB or API connection needed — all external deps are mocked at import time)
make test              # uv run pytest -v
make coverage          # pytest --cov=rag --cov-report=term-missing --cov-fail-under=70 + HTML in htmlcov/
uv run pytest tests/test_engine.py -v   # single file

# Integration tests (needs a live Postgres — see tests/test_integration.py; skipped by make test/coverage)
RUN_INTEGRATION_TESTS=1 uv run pytest tests/test_integration.py -v

# Bootstrap DB + run app in one step (db-up + init_db.py + streamlit)
make dev               # db-up db-init run
make db-init           # uv run python scripts/init_db.py (tables, seed, alembic upgrade, app_readonly)

# Lint + format
make lint              # ruff check
make format            # ruff format
make check             # lint + test (mirrors CI)

# Database (Docker)
make db-up             # start postgres container only
make db-down           # stop it
make db-reset          # destroy volume and reseed from init.sql

# Full stack
make docker-up         # docker compose up --build -d
make docker-down       # docker compose down

# Fly.io
make fly-deploy   # déployer l'image main sur Fly.io
make fly-logs     # streamer les logs en temps réel
make fly-ssh      # ouvrir un shell dans le conteneur

# Run only the engine directly (executes two example queries against live DB)
uv run python rag/engine.py
```

## Architecture

Text-to-SQL RAG pipeline — no vector store, no embeddings. LangChain orchestrates two sequential LLM calls via OpenRouter, both using `anthropic/claude-haiku-4-5`.

```
User question
  → generer_sql()   — LLM call 1: question + SCHEMA prompt → raw SQL string
  → executer_sql()  — SQLAlchemy executes SQL against PostgreSQL, returns list[dict]
  → formuler_reponse() — LLM call 2: question + SQL + results → French natural-language answer
  → repondre()      — wraps the above, catches all exceptions, returns {reponse, sql, resultats, erreur}
```

Hexagonal layering — `rag/domain` has no dependency on `rag/application` or `rag/adapters`; `rag/application` depends only on `rag/domain` and the `Protocol`s in `rag/application/ports.py`; `rag/adapters` implements those ports against real libraries (LangChain, SQLAlchemy):

- `rag/domain/schema.py` — the `SCHEMA` constant, the only DB context the LLM sees; keep it in sync with `init.sql` if the schema changes.
- `rag/domain/validation.py` — `valider_sql()` (SELECT-only, single-statement enforcement) and `valider_longueur_question()`. Pure functions, no I/O.
- `rag/domain/exceptions.py` — `SQLValidationError`, `QuestionTropLongueError`.
- `rag/application/ports.py` — `LLMPort`/`SQLExecutorPort` Protocols that adapters implement and `RagService` depends on.
- `rag/application/rag_service.py` — `RagService.repondre()`, the orchestration in the Architecture diagram above (validate → generate SQL → validate SQL → execute → formulate answer), catching exceptions and reporting them to Sentry.
- `rag/adapters/openrouter_llm_adapter.py` — `OpenRouterLLMAdapter`, implements `LLMPort` via a LangChain `BaseChatModel`.
- `rag/adapters/postgres_sql_executor_adapter.py` — `PostgresSQLExecutorAdapter`, implements `SQLExecutorPort` via SQLAlchemy (`LIMIT`-wrapping, per-connection `statement_timeout`).
- `rag/engine.py` — composition root: loads env, builds the `ChatOpenAI` client and SQLAlchemy `engine`, wires the adapters into a `RagService`, and exposes the module-level `repondre()` that `dashboard/app.py` and `scripts/init_db.py`-adjacent callers import.
- `dashboard/app.py` — Streamlit chat UI. Session state holds the full message history including raw SQL and result dicts for each assistant turn (rendered in collapsible expanders).
- `init.sql` — schema DDL + seed data. Auto-executed by Docker on first container start.

## Database

PostgreSQL (db: `fintech`). When running locally, the container maps port `5433:5432` — use `DB_PORT=5433` in `.env`. Inside Docker Compose, the app connects to the `postgres` service on the default port 5432 (`DB_HOST: postgres`, `DB_PORT: 5432` are injected by `docker-compose.yml`, overriding `.env`).

Tables and key constraints:
- `users` — id, nom, email, pays, telephone, created_at
- `comptes` — id, user_id → users.id, numero, type_compte (`courant`/`epargne`/`mobile`), solde, created_at
- `transactions` — id, compte_id → comptes.id, type_tx (`transfert`/`paiement`/`retrait`/`depot`), montant, pays_origine, pays_destination, heure (0–23), est_fraude (0/1), score_fraude (0–1), created_at
- `alertes_fraude` — id, transaction_id → transactions.id, niveau (`faible`/`moyen`/`eleve`), rapport_llm, created_at

### Privilege separation (read-only role)

`rag/engine.py` connects to Postgres with the `app_readonly` role (`READONLY_DATABASE_URL` or `READONLY_DB_USER`/`READONLY_DB_PASSWORD`), **not** the admin credentials (`DATABASE_URL`/`DB_USER`/`DB_PASSWORD`). The admin credentials are used only by `scripts/init_db.py` to create tables/seed data and to idempotently provision `app_readonly` (`GRANT SELECT` on `public` schema, `default_transaction_read_only = on`, role-level `statement_timeout`). Set `READONLY_DB_PASSWORD` in `.env`/`docker-compose.yml`/Fly secrets or role provisioning is skipped with a warning. `rag/engine.py`'s `valider_sql()` also enforces SELECT-only, single-statement SQL in code (not just via the LLM prompt) before `executer_sql()` runs it, wraps every query in a `LIMIT :max_rows` subquery, and sets a per-connection `statement_timeout` — defense in depth alongside the DB-level role restrictions.

## Environment variables (`.env`)

```
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DB_HOST=localhost
DB_PORT=5433
DB_NAME=fintech
DB_USER=
DB_PASSWORD=
READONLY_DB_PASSWORD=
DASHBOARD_PASSWORD=

# Optional — cost/abuse guardrails, all have safe defaults if unset
LLM_TIMEOUT_S=30
LLM_MAX_RETRIES=2
MAX_QUESTIONS_PAR_MINUTE=10
MAX_SQL_ROWS=20
SQL_STATEMENT_TIMEOUT_MS=5000
MAX_QUESTION_LENGTH=1000

# Optional — error reporting
SENTRY_DSN=
```

`DASHBOARD_PASSWORD` gates `dashboard/app.py` behind a shared-password screen (`st.session_state.authenticated`, 5-attempt lockout per browser session). If unset, the dashboard is open with no login — acceptable for local dev only. Set it via `fly secrets set DASHBOARD_PASSWORD=...` before any public deploy.

`MAX_QUESTIONS_PAR_MINUTE` is enforced in `dashboard/app.py` (per-browser-session sliding window over `st.session_state` timestamps), not in `rag/engine.py` — a direct call to `repondre()` outside the dashboard isn't rate-limited. The other guardrails (`LLM_TIMEOUT_S`/`LLM_MAX_RETRIES` on the `ChatOpenAI` client, `MAX_SQL_ROWS`/`SQL_STATEMENT_TIMEOUT_MS`/`MAX_QUESTION_LENGTH` in `rag/engine.py`) apply regardless of entrypoint.

`SENTRY_DSN`, if set, enables `rag/logging_config.py`'s `configure_sentry()` (called once per entrypoint alongside `configure_logging()`), which reports uncaught exceptions from the `except Exception` branch of `repondre()`. Initialized with `include_local_variables=False` — stack-frame locals (which could include generated SQL or query results) are never sent to Sentry.

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`:

- **`ci.yml`** — triggers on every push and PR to `main`. Parallel jobs:
  - `lint` — `ruff check` + `ruff format --check`
  - `test` — `pytest --cov=rag --cov-fail-under=70` (coverage minimum 70 %, no live DB or API needed)
  - `security` — `uv run pip-audit` against the resolved `uv.lock`, fails on any known CVE in a dependency (direct or transitive). Fix by bumping the affected package (`uv lock --upgrade-package <name>` or a broader `uv lock --upgrade` if several are affected) — verify `make check` still passes after, since transitive bumps can shift behavior.
  - `gitleaks` — `gitleaks/gitleaks-action@v2` scans the full push/PR diff for hardcoded secrets (API keys, passwords, connection strings). Complements GitHub's native secret scanning + push protection, which should also be enabled under repo Settings → Code security (this repo is public — that feature is free and needs no workflow file).
  - `integration` — spins up a real `postgres:15` service container, runs `scripts/init_db.py` against it (schema, seed, Alembic, `app_readonly` role), then runs `tests/test_integration.py` — the only place that proves `valider_sql()`/`executer_sql()` behave correctly against real Postgres syntax and that `app_readonly` genuinely can't `DELETE`/`INSERT`/`DROP` (connects as that role and asserts a permission error). Gated by `RUN_INTEGRATION_TESTS=1`; skipped everywhere else (`make test`, `make coverage`) since those still need no live DB.
- **`cd.yml`** — triggers via `workflow_run` on CI completion (only if CI succeeded) and on published releases. Three sequential jobs:
  1. `build-push` — builds Docker image, pushes to `ghcr.io/seydinabane/rag-fintech`. Uses `GITHUB_TOKEN`. Tags: `main`, `sha-<short>`, semver on releases.
  2. `deploy` — pulls the image from GHCR, deploys to Fly.io via `flyctl deploy --image`, then smoke-tests `https://rag-fintech.fly.dev/_stcore/health` (up to 10 retries, 10s apart) — fails the workflow run if the deploy doesn't come up healthy. Requires `FLY_API_TOKEN` secret + `production` environment on GitHub.

**Gate** : CD only runs if CI passes (`workflow_run` + `conclusion == 'success'`). Deploy only runs if build-push succeeds (`needs: [build-push]`).

**Rollback**: images are tagged both `main` and `sha-<short>` (see `build-push`'s `docker/metadata-action` config), so rolling back to a known-good build is `make fly-rollback SHA=<short-sha>` (wraps `flyctl deploy --image ghcr.io/seydinabane/rag-fintech:sha-<short-sha>`). Find the short SHA from a previous commit or from `ghcr.io/seydinabane/rag-fintech` package tags.

**Fly.io** (`fly.toml`) — region `cdg` (Paris), 512 MB RAM, health check on `/_stcore/health`, `release_command = "python scripts/init_db.py"` runs before each deploy to create tables and seed data idempotently.

**`scripts/init_db.py`** — connects via `DATABASE_URL` (Fly Postgres) or individual `DB_*` vars, creates tables if missing, seeds data only if `users` table is empty, then runs `alembic upgrade head` and provisions the `app_readonly` role (see below). Also invoked locally by `make dev`/`make db-init` and by `docker-compose.yml`'s `app` service command — it is not Fly-only.

### Schema migrations (Alembic)

`init.sql` still bootstraps a brand-new local Postgres container via `docker-entrypoint-initdb.d` (fast, zero Python dependency) and is read by `scripts/init_db.py` for the CREATE TABLE + seed pass. `migrations/versions/afcc172a6e71_baseline_schema.py` captures that same schema as an Alembic baseline (idempotent `CREATE TABLE IF NOT EXISTS`, safe to run whether or not `init.sql` already created the tables). `scripts/init_db.py` calls `alembic upgrade head` after the `init.sql` pass on every run (Fly release, `make dev`, docker-compose), so:
- **New schema changes** (e.g. adding a column to an existing prod table) must be new Alembic revisions (`uv run alembic revision -m "..."`, hand-written `op.execute`/`op.add_column` — not autogenerate, since `target_metadata` isn't wired to ORM models), not edits to the baseline or to `init.sql`. `init.sql` only needs updating too if the change should also apply to a from-scratch `docker-entrypoint-initdb.d` bootstrap.
- Migrations connect with the **admin** credentials (`DATABASE_URL`/`DB_*`, resolved in `migrations/env.py` the same way as `scripts/init_db.py`), never `app_readonly`.
- Run migrations manually with `uv run alembic upgrade head` (needs `.env` with admin DB credentials) or `uv run alembic revision -m "..."` to create a new one.

### Backups

Fly Postgres takes automated daily snapshots with Fly-managed retention. List/restore with `flyctl postgres backup list -a <postgres-app>` / `flyctl postgres backup restore <backup-id>`. There is no supplementary off-Fly backup configured — an untested backup isn't a backup, so verify a restore at least once before relying on this in an incident.

### Redundancy

`fly.toml`'s `[http_service]` runs `min_machines_running = 1` (Tier 1: always-on) instead of scale-to-zero, to eliminate the cold-start penalty on every first request after idle. This is still a single machine — Fly restarts it automatically on crash but there is a gap, not instant failover. Roughly doubles Fly compute cost vs. `min_machines_running = 0`. Real multi-machine + HA Postgres redundancy (Tier 2) would need `fly scale count 2` plus an HA Postgres cluster and isn't configured — evaluate if/when uptime requirements justify the added cost.

**`rag/engine.py`** — accepts `DATABASE_URL` env var (Fly.io injects this when a Postgres cluster is attached) with fallback to individual `DB_*` vars. Handles `postgres://` → `postgresql://` scheme conversion automatically.

**Dependabot** (`.github/dependabot.yml`) scans `pip` + `github-actions` every Monday.

**PR template** (`.github/PULL_REQUEST_TEMPLATE.md`) pre-fills Description, Type de changement, and Test plan checklist.

## Notes

- All LLM prompts and responses are in French.
- `chromadb` appears in some references but is **not used** — there is no vector retrieval step.
- Tests mirror the `rag/domain`, `rag/application`, `rag/adapters` layering (`tests/domain/`, `tests/application/`, `tests/adapters/`), each testing its layer against fakes/mocks of the ports it depends on — no live DB or LLM connections needed. `tests/test_engine.py` covers only the composition root: `TestConfigurationLLM` inspects the `ChatOpenAI` mock's call args, `TestRepondre` patches `engine_module._service` with a `MagicMock` to verify `repondre()` delegates to it. All test classes use `unittest.TestCase`, not bare pytest functions. Tests still mock both `sqlalchemy.create_engine` and `langchain_openai.ChatOpenAI` at import time (before `rag.engine` loads). `tests/test_logging_config.py` mocks `rag.logging_config.sentry_sdk.init` rather than hitting the network.
- The SQL generation prompt enforces `LIMIT 20` and `ROUND(...::numeric, 0)` for amounts — preserve these rules when editing `OpenRouterLLMAdapter.generer_sql()` (`rag/adapters/openrouter_llm_adapter.py`).
- Ruff (`pyproject.toml`) targets py311, line-length 100, rules `E, F, I, UP` with `E501` ignored — don't wrap lines just to satisfy a line-length check that's disabled.
- Structured logging (`rag/logging_config.py`, stdlib `logging`) is configured once per entrypoint (`rag/engine.py`, `dashboard/app.py`, `scripts/init_db.py`) via `configure_logging()`. `LOG_LEVEL` env var controls verbosity (default `INFO`). Questions are logged truncated (~80 chars via `_apercu()` in `rag/adapters/openrouter_llm_adapter.py`), never in full — treat free-text questions as potentially containing PII. **Never log** `OPENROUTER_API_KEY`, `DB_PASSWORD`, `READONLY_DB_PASSWORD`, `DASHBOARD_PASSWORD`, or a full `DATABASE_URL`/`DB_URL` (password embedded).
