import logging
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


def _apercu(texte: str, longueur: int = 80) -> str:
    return texte[:longueur] + ("…" if len(texte) > longueur else "")


class OpenRouterLLMAdapter:
    def __init__(self, client: BaseChatModel, schema: str) -> None:
        self._client = client
        self._schema = schema

    def generer_sql(self, question: str) -> str:
        debut = time.monotonic()
        messages = [
            SystemMessage(
                content=f"""Tu es un expert SQL PostgreSQL.
À partir du schéma suivant, génère UNIQUEMENT la requête SQL qui répond à la question.
Ne génère que le SQL brut, sans explication, sans ```sql, sans backticks.

{self._schema}

Règles :
- Utilise toujours des alias clairs
- Limite les résultats à 20 lignes max avec LIMIT 20
- Pour les montants, utilise ROUND(...::numeric, 0)
- Pour les pourcentages, multiplie par 100
"""
            ),
            HumanMessage(content=question),
        ]
        response = self._client.invoke(messages)
        sql = response.content.strip()
        logger.info(
            "generer_sql question_len=%d question_apercu=%r duree_ms=%d sql=%r",
            len(question),
            _apercu(question),
            int((time.monotonic() - debut) * 1000),
            sql,
        )
        return sql

    def formuler_reponse(self, question: str, sql: str, resultats: list[dict[str, object]]) -> str:
        debut = time.monotonic()
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
        response = self._client.invoke(messages)
        reponse = response.content.strip()
        logger.info("formuler_reponse duree_ms=%d", int((time.monotonic() - debut) * 1000))
        return reponse
