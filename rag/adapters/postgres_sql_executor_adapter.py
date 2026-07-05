import logging
import time

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


class PostgresSQLExecutorAdapter:
    def __init__(self, engine: Engine, max_rows: int, statement_timeout_ms: int) -> None:
        self._engine = engine
        self._max_rows = max_rows
        self._statement_timeout_ms = statement_timeout_ms

    def executer_sql(self, sql_valide: str) -> list[dict[str, object]]:
        debut = time.monotonic()
        requete_plafonnee = text(f"SELECT * FROM ({sql_valide}) AS _capped LIMIT :max_rows")

        with self._engine.connect() as conn:
            conn.execute(text(f"SET statement_timeout = {self._statement_timeout_ms}"))
            result = conn.execute(requete_plafonnee, {"max_rows": self._max_rows})
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(self._max_rows)]

        logger.info(
            "executer_sql duree_ms=%d lignes=%d",
            int((time.monotonic() - debut) * 1000),
            len(rows),
        )
        return rows
