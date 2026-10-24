"""Tests de l'interface avec AppTest (sans navigateur) : import, fichier incompatible, filtre sans résultat."""
import sys
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

DOSSIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER))
from test_indicateurs import EXEMPLE  # noqa: E402


def demarrer(contenu, nom="incidents.csv"):
    at = AppTest.from_file(str(DOSSIER / "app.py"), default_timeout=30).run()
    at.file_uploader[0].set_value((nom, contenu, "text/csv"))
    return at.run()


class Interface(unittest.TestCase):
    def test_sans_fichier(self):
        at = AppTest.from_file(str(DOSSIER / "app.py"), default_timeout=30).run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.metric), 0)

    def test_fichier_valide(self):
        at = demarrer(EXEMPLE)
        self.assertFalse(at.exception)
        valeurs = {m.label: m.value for m in at.metric}
        self.assertEqual(valeurs["Lignes lues"], "3")
        self.assertEqual(valeurs["Respect des SLA"], "66,67 %")

    def test_fichier_incompatible(self):
        at = demarrer(b"nom,age\nAda,36\n")
        self.assertFalse(at.exception)
        self.assertIn("Colonnes obligatoires absentes", at.error[0].value)

    def test_filtre_sans_resultat(self):
        at = demarrer(EXEMPLE)
        at.multiselect(key="filtre_category").select("B").run()
        at.multiselect(key="filtre_priority").select("3 - Moderate").run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Aucun incident" in w.value for w in at.warning))


if __name__ == "__main__":
    unittest.main()
