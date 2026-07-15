import unittest
from unittest.mock import MagicMock, patch

# Patch les dépendances externes avant l'import du module
# pour éviter les connexions réelles à la DB et à l'API LLM
with patch("sqlalchemy.create_engine"), patch("langchain_openai.ChatOpenAI") as MockChatOpenAI:
    import rag.engine as engine_module


class TestConfigurationLLM(unittest.TestCase):
    def test_llm_configure_avec_timeout_et_retries(self):
        _, kwargs = MockChatOpenAI.call_args
        self.assertIn("timeout", kwargs)
        self.assertIn("max_retries", kwargs)
        self.assertGreater(kwargs["timeout"], 0)


class TestRepondre(unittest.TestCase):
    def test_repondre_delegue_au_service(self):
        mock_service = MagicMock()
        mock_service.repondre.return_value = {
            "reponse": "ok",
            "sql": "SELECT 1",
            "resultats": [],
            "erreur": None,
        }
        with patch.object(engine_module, "_service", mock_service):
            result = engine_module.repondre("Combien de fraudes ?")

        mock_service.repondre.assert_called_once_with("Combien de fraudes ?")
        self.assertEqual(result, mock_service.repondre.return_value)


if __name__ == "__main__":
    unittest.main()
