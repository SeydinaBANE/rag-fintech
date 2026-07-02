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

**Key files:**
- `rag/engine.py` — entire RAG logic. The `SCHEMA` constant is the only DB context the LLM sees; keep it in sync with `init.sql` if the schema changes.
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
```

`DASHBOARD_PASSWORD` gates `dashboard/app.py` behind a shared-password screen (`st.session_state.authenticated`, 5-attempt lockout per browser session). If unset, the dashboard is open with no login — acceptable for local dev only. Set it via `fly secrets set DASHBOARD_PASSWORD=...` before any public deploy.

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`:

- **`ci.yml`** — triggers on every push and PR to `main`. Two parallel jobs:
  - `lint` — `ruff check` + `ruff format --check`
  - `test` — `pytest --cov=rag --cov-fail-under=70` (coverage minimum 70 %, no live DB or API needed)
- **`cd.yml`** — triggers via `workflow_run` on CI completion (only if CI succeeded) and on published releases. Three sequential jobs:
  1. `build-push` — builds Docker image, pushes to `ghcr.io/seydinabane/rag-fintech`. Uses `GITHUB_TOKEN`. Tags: `main`, `sha-<short>`, semver on releases.
  2. `deploy` — pulls the image from GHCR and deploys to Fly.io via `flyctl deploy --image`. Requires `FLY_API_TOKEN` secret + `production` environment on GitHub.

**Gate** : CD only runs if CI passes (`workflow_run` + `conclusion == 'success'`). Deploy only runs if build-push succeeds (`needs: [build-push]`).

**Fly.io** (`fly.toml`) — region `cdg` (Paris), 512 MB RAM, health check on `/_stcore/health`, `release_command = "python scripts/init_db.py"` runs before each deploy to create tables and seed data idempotently.

**`scripts/init_db.py`** — connects via `DATABASE_URL` (Fly Postgres) or individual `DB_*` vars, creates tables if missing, seeds data only if `users` table is empty, then runs `alembic upgrade head` and provisions the `app_readonly` role (see below). Also invoked locally by `make dev`/`make db-init` and by `docker-compose.yml`'s `app` service command — it is not Fly-only.

### Schema migrations (Alembic)

`init.sql` still bootstraps a brand-new local Postgres container via `docker-entrypoint-initdb.d` (fast, zero Python dependency) and is read by `scripts/init_db.py` for the CREATE TABLE + seed pass. `migrations/versions/afcc172a6e71_baseline_schema.py` captures that same schema as an Alembic baseline (idempotent `CREATE TABLE IF NOT EXISTS`, safe to run whether or not `init.sql` already created the tables). `scripts/init_db.py` calls `alembic upgrade head` after the `init.sql` pass on every run (Fly release, `make dev`, docker-compose), so:
- **New schema changes** (e.g. adding a column to an existing prod table) must be new Alembic revisions (`uv run alembic revision -m "..."`, hand-written `op.execute`/`op.add_column` — not autogenerate, since `target_metadata` isn't wired to ORM models), not edits to the baseline or to `init.sql`. `init.sql` only needs updating too if the change should also apply to a from-scratch `docker-entrypoint-initdb.d` bootstrap.
- Migrations connect with the **admin** credentials (`DATABASE_URL`/`DB_*`, resolved in `migrations/env.py` the same way as `scripts/init_db.py`), never `app_readonly`.
- Run migrations manually with `uv run alembic upgrade head` (needs `.env` with admin DB credentials) or `uv run alembic revision -m "..."` to create a new one.

### Backups

Fly Postgres takes automated daily snapshots with Fly-managed retention. List/restore with `flyctl postgres backup list -a <postgres-app>` / `flyctl postgres backup restore <backup-id>`. There is no supplementary off-Fly backup configured — an untested backup isn't a backup, so verify a restore at least once before relying on this in an incident.

**`rag/engine.py`** — accepts `DATABASE_URL` env var (Fly.io injects this when a Postgres cluster is attached) with fallback to individual `DB_*` vars. Handles `postgres://` → `postgresql://` scheme conversion automatically.

**Dependabot** (`.github/dependabot.yml`) scans `pip` + `github-actions` every Monday.

**PR template** (`.github/PULL_REQUEST_TEMPLATE.md`) pre-fills Description, Type de changement, and Test plan checklist.

## Notes

- All LLM prompts and responses are in French.
- `chromadb` appears in some references but is **not used** — there is no vector retrieval step.
- Tests mock both `sqlalchemy.create_engine` and `langchain_openai.ChatOpenAI` at import time (before `rag.engine` loads) so no live connections are needed to run the test suite. Test classes use `unittest.TestCase`, not bare pytest functions; `TestRepondre` swaps `engine_module.llm`/`engine_module.engine` per test rather than re-mocking at import time.
- The SQL generation prompt enforces `LIMIT 20` and `ROUND(...::numeric, 0)` for amounts — preserve these rules when editing `generer_sql()`.
- Ruff (`pyproject.toml`) targets py311, line-length 100, rules `E, F, I, UP` with `E501` ignored — don't wrap lines just to satisfy a line-length check that's disabled.
