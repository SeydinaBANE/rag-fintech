#!/usr/bin/env python3
"""Initialize database schema and seed data (idempotent).

Used as Fly.io release_command on every deploy.
Creates tables if they don't exist; seeds data only when tables are empty.
"""

import os
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

load_dotenv()

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

with open("/app/init.sql") as f:
    sql = f.read()

for stmt in sql.split(";"):
    stmt = stmt.strip()
    if not stmt or stmt.startswith("--"):
        continue
    is_insert = stmt.lstrip("\n").upper().startswith("INSERT")
    if is_insert and already_seeded:
        continue
    cur.execute(stmt)

conn.commit()
cur.close()
conn.close()
print("Database initialized successfully.")
