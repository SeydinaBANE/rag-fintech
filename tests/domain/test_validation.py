import unittest

from rag.domain.exceptions import QuestionTropLongueError, SQLValidationError
from rag.domain.validation import valider_longueur_question, valider_sql


class TestValiderSQL(unittest.TestCase):
    def test_accepte_un_select_simple(self):
        result = valider_sql("SELECT id FROM users")
        self.assertEqual(result, "SELECT id FROM users")

    def test_rejette_drop_table(self):
        with self.assertRaises(SQLValidationError):
            valider_sql("DROP TABLE users")

    def test_rejette_requetes_multiples(self):
        with self.assertRaises(SQLValidationError):
            valider_sql("SELECT 1; DELETE FROM users")

    def test_rejette_insert_deguise_en_select(self):
        with self.assertRaises(SQLValidationError):
            valider_sql("SELECT * FROM users; INSERT INTO users VALUES (1)")

    def test_rejette_point_virgule_interne_dans_une_chaine(self):
        with self.assertRaises(SQLValidationError):
            valider_sql("SELECT ';' AS x FROM users")

    def test_rejette_mot_cle_interdit_dans_un_select_simple(self):
        with self.assertRaises(SQLValidationError):
            valider_sql("SELECT * FROM users WHERE nom = 'DROP TABLE'")


class TestValiderLongueurQuestion(unittest.TestCase):
    def test_accepte_une_question_dans_la_limite(self):
        valider_longueur_question("Combien de fraudes ?", max_length=1000)

    def test_rejette_une_question_trop_longue(self):
        with self.assertRaises(QuestionTropLongueError):
            valider_longueur_question("a" * 1001, max_length=1000)


if __name__ == "__main__":
    unittest.main()
