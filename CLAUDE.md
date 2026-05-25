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

## Environment variables (`.env`)

```
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DB_HOST=localhost
DB_PORT=5433
DB_NAME=fintech
DB_USER=
DB_PASSWORD=
```

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`:

- **`ci.yml`** — triggers on every push and PR to `main`. Two parallel jobs:
  - `lint` — `ruff check` + `ruff format --check`
  - `test` — `pytest --cov=rag --cov-fail-under=70` (coverage minimum 70 %, no live DB or API needed)
- **`cd.yml`** — triggers via `workflow_run` on CI completion (only if CI succeeded) and on published releases. Builds and pushes to GitHub Container Registry (`ghcr.io/seydinabane/rag-fintech`). Uses `GITHUB_TOKEN` — no extra secrets required. Tags: `main`, `sha-<short>`, semver on releases.

**Gate CD → CI** : the CD never runs if lint or tests fail — enforced via `workflow_run` + `conclusion == 'success'` condition.

**Dependabot** (`.github/dependabot.yml`) scans `pip` + `github-actions` every Monday and opens PRs automatically.

**PR template** (`.github/PULL_REQUEST_TEMPLATE.md`) pre-fills Description, Type de changement, and Test plan checklist on every new PR.

## Notes

- All LLM prompts and responses are in French.
- `chromadb` appears in some references but is **not used** — there is no vector retrieval step.
- Tests mock both `sqlalchemy.create_engine` and `langchain_openai.ChatOpenAI` at import time (before `rag.engine` loads) so no live connections are needed to run the test suite.
- The SQL generation prompt enforces `LIMIT 20` and `ROUND(...::numeric, 0)` for amounts — preserve these rules when editing `generer_sql()`.
