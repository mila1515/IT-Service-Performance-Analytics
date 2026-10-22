import unittest
from pathlib import Path

import pandas as pd

from src.core.dictionnaire import initial_dictionary, records
from src.etape2_comprendre.colonnes import proposer_roles, resume_colonnes
from src.etape2_comprendre.diagnostic import diagnose

EXEMPLE = Path(__file__).parents[1] / "fixtures" / "exemple.csv"


class ColonnesTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.read_csv(EXEMPLE, dtype={"id": "string"}, keep_default_na=False, na_values=[""])
        self.dictionary = records(initial_dictionary(self.raw))
        proposer_roles(self.dictionary, diagnose(self.raw, self.dictionary, ignore_markers=True)["numeric_hints"])

    def test_mostly_numeric_text_is_proposed_as_a_number(self):
        self.assertEqual([d["Rôle"] for d in self.dictionary], ["Identifiant", "Catégorie", "Mesure", "Date"])
        self.assertEqual(self.dictionary[2]["Type attendu"], "Conserver")

    def test_one_readable_summary_per_role(self):
        fiches = {f["colonne"]: f for f in resume_colonnes(self.raw, self.dictionary)}
        self.assertEqual(fiches["id"]["exemple_repete"], ("004", 2))
        self.assertEqual(fiches["categorie"]["frequences"], [("A", 3), ("?", 2), ("B", 2)])
        montant = fiches["montant"]
        self.assertEqual((montant["nombres"], montant["non_numeriques"], montant["remplies"]), (5, 1, 6))
        self.assertEqual((montant["minimum"], montant["mediane"], montant["maximum"]), (10.5, 15., 30.))
        self.assertAlmostEqual(montant["moyenne"], 18.1)
        dates = fiches["date_commande"]
        self.assertEqual((dates["unite"], dates["periodes"]), ("mois", [("janv.", 2), ("févr.", 3), ("mars", 2)]))
        self.assertEqual(fiches["montant"]["libelle"], "Nombre")

    def test_declared_markers_count_as_missing(self):
        self.dictionary[1]["Marqueurs vides"] = "?"
        fiche = resume_colonnes(self.raw, self.dictionary)[1]
        self.assertEqual(fiche["remplies"], 5)
        self.assertNotIn("?", dict(fiche["frequences"]))


if __name__ == "__main__":
    unittest.main()
