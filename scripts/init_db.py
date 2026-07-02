#!/usr/bin/env python3
"""Initialize database schema and seed data (idempotent).

Used as Fly.io release_command on every deploy, and by `make dev`/
docker-compose locally. Creates tables from init.sql if they don't exist,
seeds data only when empty, applies any pending Alembic migrations
(schema changes beyond the baseline captured in init.sql), then
provisions the app_readonly role.
"""

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv()

# Pas d'import depuis le package rag : ce script est invoqué en `python
# scripts/init_db.py` (Fly release_command, docker-compose, make db-init),
# où le répertoire du script — pas la racine du repo — est sur sys.path,
# donc `from rag...` échouerait avec ModuleNotFoundError.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_SQL_PATH = REPO_ROOT / "init.sql"

db_url = os.getenv("DATABASE_URL") or (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME')}"
)
db_url = db_url.replace("postgres://", "postgresql://", 1)

parsed = urlparse(db_url)
conn = psycopg2.connect(
    host=parsed.hostname,
    port=parsed.port or 5432,
    dbname=parsed.path.lstrip("/"),
    user=parsed.username,
    password=parsed.password,
)
cur = conn.cursor()

cur.execute("SELECT to_regclass('public.users')")
table_exists = cur.fetchone()[0]
already_seeded = False
if table_exists:
    cur.execute("SELECT COUNT(*) FROM users")
    already_seeded = cur.fetchone()[0] > 0

with open(INIT_SQL_PATH) as f:
    lignes_sans_commentaires = [
        ligne for ligne in f.read().splitlines() if not ligne.strip().startswith("--")
    ]
    sql_script = "\n".join(lignes_sans_commentaires)

for stmt in sql_script.split(";"):
    stmt = stmt.strip()
    if not stmt:
        continue
    is_insert = stmt.lstrip("\n").upper().startswith("INSERT")
    if is_insert and already_seeded:
        continue
    cur.execute(stmt)

# Doit être committé avant d'invoquer Alembic : il ouvre sa propre connexion
# SQLAlchemy (migrations/env.py) et ses CREATE TABLE IF NOT EXISTS resteraient
# bloqués en attente du verrou tant que cette transaction reste ouverte.
conn.commit()

alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
command.upgrade(alembic_cfg, "head")
# alembic.ini's fileConfig (loaded internally by migrations/env.py) runs
# with disable_existing_loggers=True by default, which disables our own
# logger (it existed before fileConfig ran) and resets the root level to
# WARNING — restore both so the logs below aren't silently dropped.
logging.getLogger().setLevel(os.getenv("LOG_LEVEL", "INFO"))
logger.disabled = False
logger.info("Alembic migrations applied (head).")

readonly_password = os.getenv("READONLY_DB_PASSWORD")
if readonly_password:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'app_readonly'")
    role_exists = cur.fetchone() is not None
    if role_exists:
        cur.execute("ALTER ROLE app_readonly WITH LOGIN PASSWORD %s", (readonly_password,))
    else:
        cur.execute("CREATE ROLE app_readonly WITH LOGIN PASSWORD %s", (readonly_password,))
    cur.execute("ALTER ROLE app_readonly SET default_transaction_read_only = on")
    cur.execute("ALTER ROLE app_readonly SET statement_timeout = '5000'")
    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO app_readonly").format(
            sql.Identifier(parsed.path.lstrip("/"))
        )
    )
    cur.execute("GRANT USAGE ON SCHEMA public TO app_readonly")
    cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly")
    cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_readonly")
    logger.info("Role app_readonly ensured (read-only, GRANT SELECT on public schema).")
else:
    logger.warning("READONLY_DB_PASSWORD not set — skipping app_readonly role provisioning.")

conn.commit()
cur.close()
conn.close()
logger.info("Database initialized successfully.")
