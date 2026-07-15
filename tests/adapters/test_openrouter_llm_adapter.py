import unittest
from unittest.mock import MagicMock

from rag.adapters.openrouter_llm_adapter import OpenRouterLLMAdapter

SCHEMA_DE_TEST = "1. users (id, nom)"


class TestOpenRouterLLMAdapterGenererSQL(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.adapter = OpenRouterLLMAdapter(client=self.mock_client, schema=SCHEMA_DE_TEST)

    def test_retourne_une_requete_select(self):
        self.mock_client.invoke.return_value = MagicMock(
            content="SELECT COUNT(*) FROM transactions WHERE est_fraude = 1"
        )
        result = self.adapter.generer_sql("Combien de fraudes ?")
        self.assertIn("SELECT", result.upper())

    def test_supprime_les_espaces(self):
        self.mock_client.invoke.return_value = MagicMock(content="  SELECT id FROM users  ")
        result = self.adapter.generer_sql("Liste les utilisateurs")
        self.assertEqual(result, "SELECT id FROM users")

    def test_appelle_le_client_une_seule_fois_avec_le_schema(self):
        self.mock_client.invoke.return_value = MagicMock(content="SELECT 1")
        self.adapter.generer_sql("Ma question")
        self.mock_client.invoke.assert_called_once()
        messages = self.mock_client.invoke.call_args[0][0]
        self.assertIn(SCHEMA_DE_TEST, messages[0].content)


class TestOpenRouterLLMAdapterFormulerReponse(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.adapter = OpenRouterLLMAdapter(client=self.mock_client, schema=SCHEMA_DE_TEST)

    def test_retourne_la_reponse_nettoyee(self):
        self.mock_client.invoke.return_value = MagicMock(content="  42 fraudes détectées.  ")
        result = self.adapter.formuler_reponse("Combien de fraudes ?", "SELECT 1", [{"total": 42}])
        self.assertEqual(result, "42 fraudes détectées.")
        self.mock_client.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
