import unittest
from unittest.mock import MagicMock, patch

from rag.application.ports import LLMPort, SQLExecutorPort
from rag.application.rag_service import RagService


class TestRagServiceRepondre(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock(spec=LLMPort)
        self.mock_sql_executor = MagicMock(spec=SQLExecutorPort)
        self.service = RagService(
            llm=self.mock_llm, sql_executor=self.mock_sql_executor, max_question_length=1000
        )

    def _configurer_succes(self, sql="SELECT COUNT(*) FROM transactions", resultats=None):
        self.mock_llm.generer_sql.return_value = sql
        self.mock_sql_executor.executer_sql.return_value = resultats or [{"total": 42}]
        self.mock_llm.formuler_reponse.return_value = "42 fraudes détectées."

    def test_retourne_les_4_cles(self):
        self._configurer_succes()
        result = self.service.repondre("Combien de fraudes ?")
        self.assertIn("reponse", result)
        self.assertIn("sql", result)
        self.assertIn("resultats", result)
        self.assertIn("erreur", result)

    def test_erreur_est_none_en_cas_de_succes(self):
        self._configurer_succes()
        result = self.service.repondre("Combien de fraudes ?")
        self.assertIsNone(result["erreur"])
        self.assertEqual(result["reponse"], "42 fraudes détectées.")
        self.assertEqual(result["sql"], "SELECT COUNT(*) FROM transactions")
        self.assertEqual(result["resultats"], [{"total": 42}])

    def test_gere_une_erreur_llm_sans_fuite_de_details(self):
        self.mock_llm.generer_sql.side_effect = Exception("API indisponible : détail interne")
        with patch("rag.application.rag_service.sentry_sdk.capture_exception") as mock_capture:
            result = self.service.repondre("Question impossible")
        self.assertEqual(result["erreur"], "internal_error")
        self.assertNotIn("détail interne", result["reponse"])
        self.assertEqual(result["resultats"], [])
        self.assertIsNone(result["sql"])
        mock_capture.assert_called_once()
        self.mock_sql_executor.executer_sql.assert_not_called()

    def test_gere_une_requete_sql_rejetee_sans_fuite_de_details(self):
        self.mock_llm.generer_sql.return_value = "DROP TABLE users"
        result = self.service.repondre("Question malveillante")
        self.assertEqual(result["erreur"], "sql_validation_error")
        self.assertNotIn("DROP TABLE", result["reponse"])
        self.assertEqual(result["resultats"], [])
        self.assertIsNone(result["sql"])
        self.mock_sql_executor.executer_sql.assert_not_called()

    def test_gere_une_question_trop_longue(self):
        question_longue = "a" * 1001
        result = self.service.repondre(question_longue)
        self.assertEqual(result["erreur"], "question_trop_longue")
        self.assertEqual(result["resultats"], [])
        self.assertIsNone(result["sql"])
        self.mock_llm.generer_sql.assert_not_called()


if __name__ == "__main__":
    unittest.main()
