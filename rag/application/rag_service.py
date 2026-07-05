import logging
import time
from typing import TypedDict

import sentry_sdk

from rag.application.ports import LLMPort, SQLExecutorPort
from rag.domain.exceptions import QuestionTropLongueError, SQLValidationError
from rag.domain.validation import valider_longueur_question, valider_sql

logger = logging.getLogger(__name__)


class ReponseRAG(TypedDict):
    reponse: str
    sql: str | None
    resultats: list[dict[str, object]]
    erreur: str | None


class RagService:
    def __init__(
        self, llm: LLMPort, sql_executor: SQLExecutorPort, max_question_length: int
    ) -> None:
        self._llm = llm
        self._sql_executor = sql_executor
        self._max_question_length = max_question_length

    def repondre(self, question: str) -> ReponseRAG:
        debut = time.monotonic()
        try:
            valider_longueur_question(question, self._max_question_length)
            sql = self._llm.generer_sql(question)
            sql_valide = valider_sql(sql)
            resultats = self._sql_executor.executer_sql(sql_valide)
            reponse = self._llm.formuler_reponse(question, sql, resultats)
            logger.info("repondre succes=true duree_ms=%d", int((time.monotonic() - debut) * 1000))
            return {"reponse": reponse, "sql": sql, "resultats": resultats, "erreur": None}
        except SQLValidationError:
            logger.info(
                "repondre succes=false erreur=sql_validation_error duree_ms=%d",
                int((time.monotonic() - debut) * 1000),
            )
            return {
                "reponse": "Cette question nécessite une opération non autorisée.",
                "sql": None,
                "resultats": [],
                "erreur": "sql_validation_error",
            }
        except QuestionTropLongueError:
            logger.info(
                "repondre succes=false erreur=question_trop_longue duree_ms=%d",
                int((time.monotonic() - debut) * 1000),
            )
            return {
                "reponse": (
                    f"Votre question dépasse {self._max_question_length} caractères. "
                    "Reformulez-la plus brièvement."
                ),
                "sql": None,
                "resultats": [],
                "erreur": "question_trop_longue",
            }
        except Exception as e:
            logger.exception(
                "repondre succes=false erreur=internal_error duree_ms=%d",
                int((time.monotonic() - debut) * 1000),
            )
            sentry_sdk.capture_exception(e)
            return {
                "reponse": (
                    "Une erreur est survenue lors du traitement de votre question. "
                    "Veuillez réessayer ou reformuler."
                ),
                "sql": None,
                "resultats": [],
                "erreur": "internal_error",
            }
