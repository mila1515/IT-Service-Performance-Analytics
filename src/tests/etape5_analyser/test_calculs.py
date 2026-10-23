"""Étape Analyser : comparaisons, délais, évolution, constats ; sur des fichiers de domaines différents."""
import unittest
from pathlib import Path

import pandas as pd

from src.core.lecture import lire_avec_identifiants
from src.etape2_comprendre.colonnes import dictionnaire_propose
from src.etape4_visualiser.preparation import prepare
from src.etape5_analyser.calculs import (comparer, delais, duree_lisible, evolution, sections_possibles, une_ligne_par,
                                         unite_comptee)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def journal():
    """Journal d'événements : un ticket a plusieurs lignes (une par mise à jour)."""
    lignes = []
    for i in range(60):
        groupe = "G1" if i < 40 else ("G2" if i < 55 else None)
        ouvert = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i % 3)
        delai = pd.Timedelta(hours=2) if groupe == "G1" else pd.Timedelta(days=5)
        for etat in ("ouvert", "résolu"):
            lignes.append({"ticket": f"T{i:02d}", "groupe": groupe, "etat": etat, "ouvert_le": ouvert,
                           "resolu_le": ouvert + delai, "reaffectations": 1 if groupe == "G1" else 4})
    return pd.DataFrame(lignes).astype({"ticket": "string", "groupe": "string", "etat": "string"})


def charger(nom, dayfirst=False):
    raw, _ = lire_avec_identifiants((FIXTURES / nom).read_bytes())
    roles = {d["Colonne"]: d["Rôle"] for d in dictionnaire_propose(raw)}
    return prepare(raw, roles, dayfirst)[0], roles


class CalculsTests(unittest.TestCase):
    def test_one_line_per_identifier_keeps_the_last_one(self):
        data = journal()
        unites = une_ligne_par(data, "ticket")
        self.assertEqual(len(unites), 60)
        self.assertTrue((unites["etat"] == "résolu").all())
        self.assertIs(une_ligne_par(data, None), data)
        self.assertEqual(unite_comptee("ticket"), "ticket distincts")

    def test_counting_groups_describes_size_missing_and_small_groups(self):
        resultat = comparer(une_ligne_par(journal(), "ticket"), "groupe", unite="tickets")
        self.assertEqual(resultat["tableau"]["Groupe"].tolist(), ["G1", "G2", "Non renseignée"])
        self.assertEqual(resultat["constats"], [
            "« G1 » compte 40 tickets (67 % du total).",
            "5 tickets (8 %) n'ont pas de valeur dans groupe.",
            "1 groupe sur 2 a moins de 20 tickets : trop peu pour comparer."])
        self.assertEqual(resultat["graphique"]["Type"].tolist(), ["valeur", "valeur", "manquant"])

    def test_mean_by_group_needs_enough_values(self):
        resultat = comparer(une_ligne_par(journal(), "ticket"), "groupe", "moyenne", "reaffectations", "tickets")
        types = dict(zip(resultat["graphique"]["Groupe"], resultat["graphique"]["Type"]))
        self.assertEqual(types, {"G2": "fragile", "Non renseignée": "manquant", "G1": "valeur"})
        self.assertEqual(resultat["tableau"]["Groupe"].iloc[-1], "G1")
        self.assertIn("1 groupe sur 2 a moins de 20 tickets", " ".join(resultat["constats"]))

    def test_delay_by_group_and_the_weight_of_a_large_group(self):
        data = une_ligne_par(journal(), "ticket")
        data.loc[data.index[0], "resolu_le"] = data["ouvert_le"].iloc[0] - pd.Timedelta(days=1)
        data.loc[data.index[1], "resolu_le"] = pd.NaT
        resultat = delais(data, "ouvert_le", "resolu_le", "groupe", "jours", "tickets")
        self.assertEqual((resultat["calculables"], resultat["total"]), (58, 60))
        self.assertIn("1 tickets ont une date de fin avant la date de début : ignorés.", resultat["constats"])
        self.assertIn("1 tickets sans ouvert_le ou sans resolu_le lisible : ignorés.", resultat["constats"])
        self.assertEqual(duree_lisible(resultat["mediane"]), "2 h")

    def test_readable_durations(self):
        self.assertEqual([duree_lisible(v) for v in (0.0021, 0.92, 1.5, 160.64)], ["3 min", "22,08 h", "1,5 jour", "160,64 jours"])
        self.assertEqual(duree_lisible(0.5, "heures"), "30 min")

    def test_evolution_flags_concentrated_and_nearly_empty_periods(self):
        dates = pd.Series(pd.to_datetime(["2025-03-10"] * 40 + ["2025-04-10"] * 30 + ["2025-05-10"] * 28
                                         + ["2025-06-10", "2025-09-10"]))
        resultat = evolution(pd.DataFrame({"d": dates}), "d", unite="lignes")
        self.assertEqual(resultat["unite"], "mois")
        constats = " ".join(resultat["constats"])
        self.assertIn("Les 3 mois les plus chargés (mars, avr., mai) regroupent 98 % des lignes.", constats)
        self.assertIn("2 mois comptent chacun moins de 1 % des lignes", constats)


class AutresFichiersTests(unittest.TestCase):
    """Les analyses dépendent des types, pas des noms de colonnes : ventes, élèves, capteurs."""

    def test_sections_follow_the_column_types(self):
        attendu = {"ventes.csv": {"comparer": True, "delai": True, "evolution": True},
                   "eleves.csv": {"comparer": True, "delai": False, "evolution": False},
                   "capteurs.csv": {"comparer": False, "delai": False, "evolution": True}}
        for nom, sections in attendu.items():
            with self.subTest(nom):
                self.assertEqual(sections_possibles(charger(nom)[1]), sections)

    def test_every_available_analysis_runs_on_each_file(self):
        for nom in ("ventes.csv", "eleves.csv", "capteurs.csv"):
            with self.subTest(nom):
                data, roles = charger(nom, dayfirst=True)
                categories = [c for c, r in roles.items() if r == "Catégorie"]
                mesures = [c for c, r in roles.items() if r == "Mesure"]
                dates = [c for c, r in roles.items() if r == "Date"]
                for groupe in categories:
                    self.assertTrue(comparer(data, groupe)["constats"])
                    for mesure in mesures:
                        self.assertTrue(comparer(data, groupe, "mediane", mesure)["constats"])
                if len(dates) >= 2:
                    resultat = delais(data, dates[0], dates[1], categories[0] if categories else None)
                    self.assertEqual(resultat["calculables"], len(data))
                for date in dates:
                    self.assertTrue(evolution(data, date)["constats"])

    def test_sales_delay_is_computed_from_french_dates(self):
        data, _ = charger("ventes.csv", dayfirst=True)
        resultat = delais(data, "date_commande", "date_livraison", "magasin")
        self.assertEqual(resultat["calculables"], 60)
        self.assertTrue(1 <= resultat["mediane"] <= 8)


if __name__ == "__main__":
    unittest.main()
