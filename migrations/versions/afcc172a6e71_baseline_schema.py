"""baseline schema

Captures the schema already created by init.sql for existing deployments
(CREATE TABLE IF NOT EXISTS keeps this idempotent whether or not init.sql
already ran) and is the schema Alembic will create from scratch on a
brand-new database that skips the init.sql bootstrap. Keep init.sql and
this migration in sync when the schema changes; future schema changes
should be new revisions, not edits to this file.

Revision ID: afcc172a6e71
Revises:
Create Date: 2026-07-02 11:20:03.643875

"""

from alembic import op

revision: str = "afcc172a6e71"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            nom VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            pays VARCHAR(50),
            telephone VARCHAR(20),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS comptes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            numero VARCHAR(20) UNIQUE NOT NULL,
            type_compte VARCHAR(30),
            solde NUMERIC(15, 2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            compte_id INTEGER REFERENCES comptes(id),
            type_tx VARCHAR(20) CHECK (type_tx IN ('transfert', 'paiement', 'retrait', 'depot')),
            montant NUMERIC(15, 2) NOT NULL,
            pays_origine VARCHAR(50),
            pays_destination VARCHAR(50),
            heure INTEGER CHECK (heure BETWEEN 0 AND 23),
            est_fraude SMALLINT DEFAULT 0 CHECK (est_fraude IN (0, 1)),
            score_fraude NUMERIC(5, 4) DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS alertes_fraude (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER REFERENCES transactions(id),
            niveau VARCHAR(20) CHECK (niveau IN ('faible', 'moyen', 'eleve')),
            rapport_llm TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alertes_fraude")
    op.execute("DROP TABLE IF EXISTS transactions")
    op.execute("DROP TABLE IF EXISTS comptes")
    op.execute("DROP TABLE IF EXISTS users")
