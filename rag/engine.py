import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine

from rag.adapters.openrouter_llm_adapter import OpenRouterLLMAdapter
from rag.adapters.postgres_sql_executor_adapter import PostgresSQLExecutorAdapter
from rag.application.rag_service import RagService, ReponseRAG
from rag.domain.schema import SCHEMA
from rag.logging_config import configure_logging, configure_sentry

load_dotenv()
configure_logging()
configure_sentry()

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "1000"))


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

llm = ChatOpenAI(
    model="anthropic/claude-haiku-4-5",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL"),
    temperature=0,
    timeout=int(os.getenv("LLM_TIMEOUT_S", "30")),
    max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
)

llm_adapter = OpenRouterLLMAdapter(client=llm, schema=SCHEMA)
sql_executor_adapter = PostgresSQLExecutorAdapter(
    engine=engine, max_rows=MAX_SQL_ROWS, statement_timeout_ms=SQL_STATEMENT_TIMEOUT_MS
)
_service = RagService(
    llm=llm_adapter, sql_executor=sql_executor_adapter, max_question_length=MAX_QUESTION_LENGTH
)


def repondre(question: str) -> ReponseRAG:
    return _service.repondre(question)


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
