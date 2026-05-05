import os
from sqlalchemy import create_engine, text
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)

llm = ChatOpenAI(
    model="anthropic/claude-haiku-4-5",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
    temperature=0
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
        SystemMessage(content=f"""Tu es un expert SQL PostgreSQL.
À partir du schéma suivant, génère UNIQUEMENT la requête SQL qui répond à la question.
Ne génère que le SQL brut, sans explication, sans ```sql, sans backticks.

{SCHEMA}

Règles :
- Utilise toujours des alias clairs
- Limite les résultats à 20 lignes max avec LIMIT 20
- Pour les montants, utilise ROUND(...::numeric, 0)
- Pour les pourcentages, multiplie par 100
"""),
        HumanMessage(content=question)
    ]
    response = llm.invoke(messages)
    return response.content.strip()

def executer_sql(sql: str) -> list:
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return rows

def formuler_reponse(question: str, sql: str, resultats: list) -> str:
    messages = [
        SystemMessage(content="""Tu es un assistant analyste financier pour une fintech africaine.
Tu reçois une question, la requête SQL exécutée et les résultats.
Formule une réponse claire, professionnelle et concise en français.
Inclus les chiffres clés. Sois direct et précis."""),
        HumanMessage(content=f"""Question : {question}

SQL exécuté : {sql}

Résultats : {resultats}

Formule une réponse naturelle et professionnelle.""")
    ]
    response = llm.invoke(messages)
    return response.content.strip()

def repondre(question: str) -> dict:
    try:
        sql      = generer_sql(question)
        resultats = executer_sql(sql)
        reponse  = formuler_reponse(question, sql, resultats)
        return {
            "reponse":   reponse,
            "sql":       sql,
            "resultats": resultats,
            "erreur":    None
        }
    except Exception as e:
        return {
            "reponse":   f"Je n'ai pas pu répondre à cette question. Erreur : {str(e)}",
            "sql":       None,
            "resultats": [],
            "erreur":    str(e)
        }
        


if __name__ == "__main__":
    questions = [
        'Quel client a le plus de transactions frauduleuses ?',
        'Quel est le montant moyen des fraudes par heure de la nuit ?'
    ]
    for q in questions:
        print(f'Q: {q}')
        r = repondre(q)
        print(f'R: {r["reponse"]}')
        print(f'SQL: {r["sql"]}')
        print('---')