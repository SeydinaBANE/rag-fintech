import os
import unittest

from sqlalchemy import text

import rag.engine as engine_module

_INTEGRATION_ENABLED = bool(os.getenv("RUN_INTEGRATION_TESTS"))
_SKIP_REASON = "set RUN_INTEGRATION_TESTS=1 to run against a real Postgres"


@unittest.skipUnless(_INTEGRATION_ENABLED, _SKIP_REASON)
class TestExecuterSQLContreVraiePostgres(unittest.TestCase):
    def test_select_simple_fonctionne(self):
        rows = engine_module.executer_sql("SELECT COUNT(*) AS total FROM users")
        self.assertEqual(len(rows), 1)
        self.assertIn("total", rows[0])

    def test_plafond_de_lignes_est_applique(self):
        rows = engine_module.executer_sql("SELECT generate_series(1, 100) AS n")
        self.assertEqual(len(rows), engine_module.MAX_SQL_ROWS)

    def test_drop_table_rejete_avant_execution(self):
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.executer_sql("DROP TABLE users")

    def test_multi_statement_rejete_avant_execution(self):
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.executer_sql("SELECT 1; DELETE FROM users")


@unittest.skipUnless(_INTEGRATION_ENABLED, _SKIP_REASON)
class TestRoleAppReadonly(unittest.TestCase):
    """Preuve que le rôle app_readonly (créé par scripts/init_db.py) ne
    peut pas écrire, indépendamment de valider_sql() côté application."""

    def test_refuse_le_delete(self):
        with self.assertRaises(Exception):
            with engine_module.engine.connect() as conn:
                conn.execute(text("DELETE FROM users WHERE id = 1"))

    def test_refuse_le_insert(self):
        with self.assertRaises(Exception):
            with engine_module.engine.connect() as conn:
                conn.execute(text("INSERT INTO users (nom, email) VALUES ('x', 'x@example.com')"))

    def test_refuse_le_drop(self):
        with self.assertRaises(Exception):
            with engine_module.engine.connect() as conn:
                conn.execute(text("DROP TABLE users"))

    def test_select_reste_autorise(self):
        with engine_module.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            self.assertIsNotNone(result.scalar())


if __name__ == "__main__":
    unittest.main()
