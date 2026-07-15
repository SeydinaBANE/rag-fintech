import unittest
from unittest.mock import MagicMock

from rag.adapters.postgres_sql_executor_adapter import PostgresSQLExecutorAdapter


class TestPostgresSQLExecutorAdapter(unittest.TestCase):
    def _mock_engine(self, colonnes, lignes):
        mock_result = MagicMock()
        mock_result.keys.return_value = colonnes
        mock_result.fetchmany.return_value = lignes

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine, mock_conn

    def test_retourne_une_liste_de_dicts(self):
        mock_engine, _ = self._mock_engine(["id", "nom"], [(1, "Aminata"), (2, "Moussa")])
        adapter = PostgresSQLExecutorAdapter(mock_engine, max_rows=20, statement_timeout_ms=5000)
        result = adapter.executer_sql("SELECT id, nom FROM users")
        self.assertEqual(result, [{"id": 1, "nom": "Aminata"}, {"id": 2, "nom": "Moussa"}])

    def test_retourne_liste_vide_si_aucun_resultat(self):
        mock_engine, _ = self._mock_engine(["id"], [])
        adapter = PostgresSQLExecutorAdapter(mock_engine, max_rows=20, statement_timeout_ms=5000)
        result = adapter.executer_sql("SELECT id FROM users WHERE 1=0")
        self.assertEqual(result, [])

    def test_definit_le_timeout_avant_la_requete(self):
        mock_engine, mock_conn = self._mock_engine(["id"], [(1,)])
        adapter = PostgresSQLExecutorAdapter(mock_engine, max_rows=20, statement_timeout_ms=5000)
        adapter.executer_sql("SELECT id FROM users")
        self.assertEqual(mock_conn.execute.call_count, 2)


if __name__ == "__main__":
    unittest.main()
