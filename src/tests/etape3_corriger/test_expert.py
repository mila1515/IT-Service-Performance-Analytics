"""Mode expert léger : règles simples, espaces en trop, sans changement par défaut."""
import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.lecture import lire_avec_identifiants
from src.core.regles import regles_simples
from src.etape2_comprendre.colonnes import dictionnaire_propose
from src.etape2_comprendre.diagnostic import diagnose
from src.etape2_comprendre.points import compter_espaces, detecter_points, exemples, verifier_regles
from src.etape3_corriger.correction import (executer, motif_lisible, phrases_journal, plan_nettoyage, regles_signalees,
                                            resume_resultat)

EXEMPLE = Path(__file__).parents[1] / "fixtures" / "exemple.csv"
REGLES = {"id": {"unique": True}, "montant": {"bornes": [0, 25]}, "date_commande": {"remplie": True}}


def charger():
    raw, _ = lire_avec_identifiants(EXEMPLE.read_bytes())
    dictionary = dictionnaire_propose(raw)
    return raw, dictionary, diagnose(raw, dictionary, True)


class ReglesSimplesTests(unittest.TestCase):
    def test_rules_become_readable_controls_with_sorted_bounds(self):
        controles = regles_simples({"montant": {"remplie": True, "unique": False, "bornes": [25, 0]}})
        self.assertEqual([c["id"] for c in controles], ["montant : doit être remplie", "montant : entre 0 et 25"])
        self.assertEqual((controles[1]["low"], controles[1]["high"]), (0., 25.))
        self.assertEqual(regles_simples({"x": {"remplie": False, "unique": False, "bornes": None}}), [])

    def test_rule_results_on_the_sample(self):
        raw, dictionary, _ = charger()
        resultats = verifier_regles(raw, dictionary, regles_simples(REGLES))
        self.assertEqual(resultats, {"id : valeurs uniques": [4, 6], "montant : entre 0 et 25": [7],
                                     "date_commande : doit être remplie": []})

    def test_expert_points_only_in_expert_mode(self):
        raw, dictionary, diagnostic = charger()
        controles = regles_simples(REGLES)
        simple = detecter_points(raw, dictionary, {}, diagnostic, controles)
        self.assertNotIn("regles", [p["type"] for p in simple])
        expert = detecter_points(raw, dictionary, {}, diagnostic, controles, expert=True)
        regles = next(p for p in expert if p["type"] == "regles")
        self.assertEqual([l["cle"] for l in regles["lignes"]], ["id : valeurs uniques", "montant : entre 0 et 25"])
        self.assertIn("2 lignes ne respectent pas (lignes 4, 6)", regles["lignes"][0]["texte"])
        self.assertEqual(exemples(raw, diagnostic, "regles", "id : valeurs uniques", numeros=[4, 6]).index.tolist(), [4, 6])

    def test_keeping_flagged_rows_changes_nothing(self):
        raw, dictionary, diagnostic = charger()
        plan = plan_nettoyage(dictionary, {"regles": {"id : valeurs uniques": "garder"}}, diagnostic["suspects"],
                              regles_simples(REGLES))
        cleaned, rejects, _ = executer(raw, plan)
        assert_frame_equal(cleaned, raw)
        self.assertTrue(rejects.empty)

    def test_excluding_flagged_rows_keeps_reference_and_readable_reason(self):
        raw, dictionary, diagnostic = charger()
        choix = {"regles": {"id : valeurs uniques": "ecarter", "montant : entre 0 et 25": "ecarter"}}
        plan = plan_nettoyage(dictionary, choix, diagnostic["suspects"], regles_simples(REGLES))
        cleaned, rejects, log = executer(raw, plan)
        self.assertEqual(rejects[("Traçabilité", "Enregistrement source")].tolist(), [4, 6, 7])
        resultat = resume_resultat(raw, plan, cleaned, rejects)
        self.assertEqual(dict(resultat["motifs"]), {"règle non respectée (id : valeurs uniques)": 2,
                                                    "règle non respectée (montant : entre 0 et 25)": 1})
        self.assertIn("2 lignes mises de côté : règle non respectée (id : valeurs uniques)", phrases_journal(log))
        self.assertEqual(motif_lisible("Valeur manquante : x"), "x vide")


class JournalReglesTests(unittest.TestCase):
    def test_kept_rule_violations_are_written_in_the_journal(self):
        resultats = {"id : valeurs uniques": [4, 6], "montant : entre 0 et 25": [7], "date : doit être remplie": []}
        signalees = regles_signalees(resultats, {"regles": {"montant : entre 0 et 25": "ecarter"}})
        self.assertEqual(signalees, [("id : valeurs uniques", 2)])
        self.assertEqual(phrases_journal([], signalees), ["id : valeurs uniques — 2 lignes signalées, gardées"])


class EspacesTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.DataFrame({"groupe": [" A", "A", "B ", "   ", None], "n": [1, 2, 3, 4, 5]})
        self.dictionary = dictionnaire_propose(self.raw)
        self.diagnostic = diagnose(self.raw, self.dictionary, True)

    def test_spaces_are_counted_and_offered_in_expert_mode(self):
        self.assertEqual(compter_espaces(self.raw), 2)
        points = detecter_points(self.raw, self.dictionary, {}, self.diagnostic, expert=True)
        espaces = next(p for p in points if p["type"] == "espaces")
        self.assertEqual(espaces["lignes"][0]["texte"], "2 valeurs avec des espaces au début ou à la fin")
        self.assertEqual(exemples(self.raw, self.diagnostic, "espaces", "espaces").index.tolist(), [1, 3])
        self.assertEqual(compter_espaces(pd.DataFrame({"n": [1, 2]})), 0)

    def test_removing_spaces_merges_identical_values(self):
        plan = plan_nettoyage(self.dictionary, {"espaces": {"espaces": "supprimer"}}, self.diagnostic["suspects"])
        cleaned, _, log = executer(self.raw, plan)
        self.assertEqual(cleaned["groupe"].dropna().tolist(), ["A", "A", "B"])
        self.assertIn("groupe : espaces en trop supprimés (2 valeurs)", phrases_journal(log))


if __name__ == "__main__":
    unittest.main()
