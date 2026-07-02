import os
import re

import sqlparse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, text

load_dotenv()


class SQLValidationError(Exception):
    pass


# L'app se connecte avec le rôle app_readonly (SELECT uniquement, créé par
# scripts/init_db.py) — les identifiants admin DATABASE_URL/DB_* ne sont
# utilisés que par scripts/init_db.py, jamais par l'app en exécution.
_db_url = os.getenv("READONLY_DATABASE_URL") or (
    f"postgresql://{os.getenv('READONLY_DB_USER', 'app_readonly')}:{os.getenv('READONLY_DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
DB_URL = _db_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(DB_URL)

MAX_SQL_ROWS = int(os.getenv("MAX_SQL_ROWS", "20"))
SQL_STATEMENT_TIMEOUT_MS = int(os.getenv("SQL_STATEMENT_TIMEOUT_MS", "5000"))

_MOTS_CLES_INTERDITS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|CALL|EXECUTE)\b",
    re.IGNORECASE,
)

llm = ChatOpenAI(
    model="anthropic/claude-haiku-4-5",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
    temperature=0,
)

SCHEMA = """
Base de données fintech PostgreSQL. Tables disponibles :

1. users (id, nom, email, pays, telephone, created_at)
2. comptes (id, user_id, numero, type_compte, solde, created_at)
3. transactions (id, compte_id, type_tx, montant, pays_origine, pays_destination, heure, est_fraude, score_fraude, created_at)
4. alertes_fraude (id, transaction_id, niveau, rapport_llm, created_at)

Relations :
- comptes.user_id → users.id
- transactions.compte_id → comptes.id
- alertes_fraude.transaction_id → transactions.id

Valeurs importantes :
- est_fraude : 0 = normal, 1 = fraude
- type_tx : transfert, paiement, retrait, depot
- heure : 0-23
"""


def generer_sql(question: str) -> str:
    messages = [
        SystemMessage(
            content=f"""Tu es un expert SQL PostgreSQL.
À partir du schéma suivant, génère UNIQUEMENT la requête SQL qui répond à la question.
Ne génère que le SQL brut, sans explication, sans ```sql, sans backticks.

{SCHEMA}

Règles :
- Utilise toujours des alias clairs
- Limite les résultats à 20 lignes max avec LIMIT 20
- Pour les montants, utilise ROUND(...::numeric, 0)
- Pour les pourcentages, multiplie par 100
"""
        ),
        HumanMessage(content=question),
    ]
    response = llm.invoke(messages)
    return response.content.strip()


def valider_sql(sql: str) -> str:
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise SQLValidationError("La requête doit contenir une seule instruction SQL.")

    statement = statements[0]
    if statement.get_type() != "SELECT":
        raise SQLValidationError("Seules les requêtes SELECT sont autorisées.")

    corps = str(statement).strip().rstrip(";")
    if ";" in corps:
        raise SQLValidationError("Les requêtes multiples ne sont pas autorisées.")
    if _MOTS_CLES_INTERDITS.search(corps):
        raise SQLValidationError("La requête contient une opération non autorisée.")

    return corps


def executer_sql(sql: str) -> list:
    sql_valide = valider_sql(sql)
    requete_plafonnee = text(f"SELECT * FROM ({sql_valide}) AS _capped LIMIT :max_rows")

    with engine.connect() as conn:
        conn.execute(text(f"SET statement_timeout = {SQL_STATEMENT_TIMEOUT_MS}"))
        result = conn.execute(requete_plafonnee, {"max_rows": MAX_SQL_ROWS})
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchmany(MAX_SQL_ROWS)]
    return rows


def formuler_reponse(question: str, sql: str, resultats: list) -> str:
    messages = [
        SystemMessage(
            content="""Tu es un assistant analyste financier pour une fintech africaine.
Tu reçois une question, la requête SQL exécutée et les résultats.
Formule une réponse claire, professionnelle et concise en français.
Inclus les chiffres clés. Sois direct et précis."""
        ),
        HumanMessage(
            content=f"""Question : {question}

SQL exécuté : {sql}

Résultats : {resultats}

Formule une réponse naturelle et professionnelle."""
        ),
    ]
    response = llm.invoke(messages)
    return response.content.strip()


def repondre(question: str) -> dict:
    try:
        sql = generer_sql(question)
        resultats = executer_sql(sql)
        reponse = formuler_reponse(question, sql, resultats)
        return {"reponse": reponse, "sql": sql, "resultats": resultats, "erreur": None}
    except Exception as e:
        return {
            "reponse": f"Je n'ai pas pu répondre à cette question. Erreur : {str(e)}",
            "sql": None,
            "resultats": [],
            "erreur": str(e),
        }


if __name__ == "__main__":
    questions = [
        "Quel client a le plus de transactions frauduleuses ?",
        "Quel est le montant moyen des fraudes par heure de la nuit ?",
    ]
    for q in questions:
        print(f"Q: {q}")
        r = repondre(q)
        print(f"R: {r['reponse']}")
        print(f"SQL: {r['sql']}")
        print("---")
