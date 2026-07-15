from typing import Protocol


class LLMPort(Protocol):
    def generer_sql(self, question: str) -> str: ...

    def formuler_reponse(
        self, question: str, sql: str, resultats: list[dict[str, object]]
    ) -> str: ...


class SQLExecutorPort(Protocol):
    def executer_sql(self, sql_valide: str) -> list[dict[str, object]]: ...
