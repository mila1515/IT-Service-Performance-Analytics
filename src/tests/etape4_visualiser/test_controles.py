import unittest

import pandas as pd

from src.core.dates import compter_par_periode, libelle_periode, unite_periode
from src.core.texte import nombre_lisible, pluriel
from src.etape4_visualiser.controles import graphiques_controle
from src.etape4_visualiser.preparation import prepare

ROLES = {"id": "Identifiant", "categorie": "Catégorie", "montant": "Mesure", "date_commande": "Date"}


def donnees():
    raw = pd.DataFrame({"id": ["001", "002", "003", "004", "005", "004", "006"],
                        "categorie": ["A", None, "B", "A", None, "A", "B"],
                        "montant": [10.5, 20., None, 15., None, 15., 30.],
                        "date_commande": ["2026-01-05", "2026-01-17", "2026-02-03", "2026-02-20",
                                          "2026-03-01", "2026-02-20", "2026-03-15"]})
    return prepare(raw, ROLES)[0]


class ControlesTests(unittest.TestCase):
    def test_three_charts_chosen_from_roles(self):
        graphiques = graphiques_controle(donnees(), ROLES)
        self.assertEqual([g["genre"] for g in graphiques], ["barres", "moyennes", "periodes"])
        repartition, moyennes, periodes = graphiques
        self.assertEqual(repartition["donnees"]["Lignes"].tolist(), [3, 2, 2])
        self.assertEqual(repartition["donnees"]["Type"].tolist(), ["valeur", "valeur", "manquant"])
        self.assertIn("« A » est la valeur la plus fréquente : 3 lignes sur 7.", repartition["a_retenir"])
        self.assertEqual(moyennes["donnees"]["Groupe"].tolist(), ["B", "Non renseignée", "A"])
        self.assertEqual(moyennes["donnees"]["Fragile"].tolist(), [True, True, False])
        self.assertIn("trop fragiles", moyennes["a_retenir"][0])
        self.assertEqual(moyennes["sous_titre"], "5 valeurs renseignées · 2 cases vides ignorées")
        self.assertEqual(periodes["donnees"]["Lignes"].tolist(), [2, 3, 2])
        self.assertTrue(periodes["a_retenir"][0].startswith("Févr. compte le plus de lignes (3)"))

    def test_distribution_without_category_and_no_chart_without_data(self):
        data = donnees()
        roles = {"montant": "Mesure"}
        genre = [g["genre"] for g in graphiques_controle(data, roles)]
        self.assertEqual(genre, ["histogramme"])
        self.assertEqual(graphiques_controle(data.assign(montant=float("nan")), roles), [])

    def test_periods_include_empty_ones_and_readable_labels(self):
        dates = pd.Series(pd.to_datetime(["2026-01-05", "2026-03-15"]))
        frame, unite = compter_par_periode(dates)
        self.assertEqual((unite, frame["Lignes"].tolist()), ("mois", [1, 0, 1]))
        self.assertEqual(unite_periode(pd.Timestamp("2020-01-01"), pd.Timestamp("2026-01-01")), "année")
        self.assertEqual(libelle_periode(pd.Timestamp("2026-03-05"), "jour"), "5 mars")
        self.assertEqual(compter_par_periode(pd.Series([pd.NaT]))[1], None)

    def test_number_formatting(self):
        self.assertEqual(nombre_lisible(141712), "141 712")
        self.assertEqual(nombre_lisible(18.1), "18,1")
        self.assertEqual(nombre_lisible(15.0), "15")
        self.assertEqual(pluriel(1, "case"), "1 case")
        self.assertEqual(pluriel(2, "ligne identique", "lignes identiques"), "2 lignes identiques")


if __name__ == "__main__":
    unittest.main()
