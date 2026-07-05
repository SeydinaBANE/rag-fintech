import logging
import re

import sqlparse

from rag.domain.exceptions import QuestionTropLongueError, SQLValidationError

logger = logging.getLogger(__name__)

_MOTS_CLES_INTERDITS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|CALL|EXECUTE)\b",
    re.IGNORECASE,
)


def valider_longueur_question(question: str, max_length: int) -> None:
    if len(question) > max_length:
        logger.warning(
            "valider_longueur_question rejet raison=question_trop_longue longueur=%d", len(question)
        )
        raise QuestionTropLongueError(
            f"La question dépasse la longueur maximale autorisée ({max_length} caractères)."
        )


def valider_sql(sql: str) -> str:
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        logger.warning("valider_sql rejet raison=instructions_multiples sql=%r", sql)
        raise SQLValidationError("La requête doit contenir une seule instruction SQL.")

    statement = statements[0]
    if statement.get_type() != "SELECT":
        logger.warning("valider_sql rejet raison=non_select sql=%r", sql)
        raise SQLValidationError("Seules les requêtes SELECT sont autorisées.")

    corps = str(statement).strip().rstrip(";")
    if ";" in corps:
        logger.warning("valider_sql rejet raison=point_virgule_interne sql=%r", sql)
        raise SQLValidationError("Les requêtes multiples ne sont pas autorisées.")
    if _MOTS_CLES_INTERDITS.search(corps):
        logger.warning("valider_sql rejet raison=mot_cle_interdit sql=%r", sql)
        raise SQLValidationError("La requête contient une opération non autorisée.")

    return corps
