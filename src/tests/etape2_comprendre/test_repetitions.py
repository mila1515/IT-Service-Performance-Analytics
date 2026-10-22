"""Pourquoi un identifiant se répète : groupes, colonnes qui changent, exemple, sans modifier les données."""
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.lecture import lire_avec_identifiants
from src.etape2_comprendre.repetitions import part_lisible, variations

EXEMPLE = Path(__file__).parents[1] / "fixtures" / "exemple.csv"


class VariationsTests(unittest.TestCase):
    def test_identical_copies_have_no_changing_column(self):
        raw, _ = lire_avec_identifiants(EXEMPLE.read_bytes())
        resultat = variations(raw, "id")
        self.assertEqual((resultat["groupes"], resultat["lignes"]), (1, 2))
        self.assertEqual(resultat["changent"], [])
        self.assertEqual(resultat["identiques"], ["categorie", "montant", "date_commande"])
        self.assertEqual((resultat["exemple"], resultat["exemple_total"]), ("004", 2))
        self.assertEqual(resultat["exemple_lignes"].index.tolist(), [3, 5])

    def test_event_log_shows_what_changes_and_keeps_data(self):
        data = pd.DataFrame({"ticket": ["T1", "T1", "T1", "T2", "T2", "T3", None, None],
                             "etat": ["ouvert", "en cours", "fermé", "ouvert", "fermé", "ouvert", "x", "y"],
                             "equipe": ["A", "A", "B", "C", "C", "D", "E", "E"],
                             "ouvert_le": ["01/01", "01/01", "01/01", "02/01", "02/01", "03/01", None, None]})
        copie = data.copy()
        resultat = variations(data, "ticket")
        assert_frame_equal(data, copie)
        self.assertEqual((resultat["groupes"], resultat["lignes"]), (2, 5))
        self.assertEqual(resultat["changent"], [("etat", 1.0), ("equipe", 0.5)])
        self.assertEqual(resultat["identiques"], ["ouvert_le"])
        self.assertEqual(resultat["exemple"], "T1")
        self.assertEqual(resultat["exemple_lignes"].columns.tolist(), ["ticket", "etat", "equipe"])

    def test_no_repetition_and_readable_shares(self):
        self.assertIsNone(variations(pd.DataFrame({"id": ["a", "b", None, None], "x": [1, 2, 3, 4]}), "id"))
        self.assertEqual([part_lisible(p) for p in (1.0, 0.996, 0.5, 0.004)], ["100 %", "99 %", "50 %", "moins de 1 %"])


if __name__ == "__main__":
    unittest.main()
