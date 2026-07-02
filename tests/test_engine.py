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


class TestGenererSQL(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        engine_module.llm = self.mock_llm

    def test_retourne_une_requete_select(self):
        self.mock_llm.invoke.return_value = MagicMock(
            content="SELECT COUNT(*) FROM transactions WHERE est_fraude = 1"
        )
        result = engine_module.generer_sql("Combien de fraudes ?")
        self.assertIn("SELECT", result.upper())

    def test_supprime_les_espaces(self):
        self.mock_llm.invoke.return_value = MagicMock(content="  SELECT id FROM users  ")
        result = engine_module.generer_sql("Liste les utilisateurs")
        self.assertEqual(result, "SELECT id FROM users")

    def test_appelle_le_llm_avec_la_question(self):
        self.mock_llm.invoke.return_value = MagicMock(content="SELECT 1")
        engine_module.generer_sql("Ma question")
        self.mock_llm.invoke.assert_called_once()


class TestValiderSQL(unittest.TestCase):
    def test_accepte_un_select_simple(self):
        result = engine_module.valider_sql("SELECT id FROM users")
        self.assertEqual(result, "SELECT id FROM users")

    def test_rejette_drop_table(self):
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.valider_sql("DROP TABLE users")

    def test_rejette_requetes_multiples(self):
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.valider_sql("SELECT 1; DELETE FROM users")

    def test_rejette_insert_deguise_en_select(self):
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.valider_sql("SELECT * FROM users; INSERT INTO users VALUES (1)")


class TestExecuterSQL(unittest.TestCase):
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
        engine_module.engine = mock_engine
        return mock_conn

    def test_retourne_une_liste_de_dicts(self):
        self._mock_engine(["id", "nom"], [(1, "Aminata"), (2, "Moussa")])
        result = engine_module.executer_sql("SELECT id, nom FROM users")
        self.assertEqual(result, [{"id": 1, "nom": "Aminata"}, {"id": 2, "nom": "Moussa"}])

    def test_retourne_liste_vide_si_aucun_resultat(self):
        self._mock_engine(["id"], [])
        result = engine_module.executer_sql("SELECT id FROM users WHERE 1=0")
        self.assertEqual(result, [])

    def test_definit_le_timeout_avant_la_requete(self):
        mock_conn = self._mock_engine(["id"], [(1,)])
        engine_module.executer_sql("SELECT id FROM users")
        self.assertEqual(mock_conn.execute.call_count, 2)

    def test_rejette_le_sql_non_select_avant_execution(self):
        mock_conn = self._mock_engine(["id"], [(1,)])
        with self.assertRaises(engine_module.SQLValidationError):
            engine_module.executer_sql("DROP TABLE users")
        mock_conn.execute.assert_not_called()


class TestRepondre(unittest.TestCase):
    def _setup_mocks(self, sql_content="SELECT COUNT(*) FROM transactions", lignes=None):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=sql_content)
        engine_module.llm = mock_llm

        mock_result = MagicMock()
        mock_result.keys.return_value = ["total"]
        mock_result.fetchmany.return_value = lignes or [(42,)]

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        engine_module.engine = mock_engine

    def test_retourne_les_4_cles(self):
        self._setup_mocks()
        result = engine_module.repondre("Combien de fraudes ?")
        self.assertIn("reponse", result)
        self.assertIn("sql", result)
        self.assertIn("resultats", result)
        self.assertIn("erreur", result)

    def test_erreur_est_none_en_cas_de_succes(self):
        self._setup_mocks()
        result = engine_module.repondre("Combien de fraudes ?")
        self.assertIsNone(result["erreur"])

    def test_gere_une_erreur_llm(self):
        engine_module.llm = MagicMock()
        engine_module.llm.invoke.side_effect = Exception("API indisponible")
        result = engine_module.repondre("Question impossible")
        self.assertIsNotNone(result["erreur"])
        self.assertIn("Erreur", result["reponse"])
        self.assertEqual(result["resultats"], [])
        self.assertIsNone(result["sql"])


if __name__ == "__main__":
    unittest.main()
