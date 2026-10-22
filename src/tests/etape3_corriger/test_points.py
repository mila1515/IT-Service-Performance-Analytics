import unittest
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.dictionnaire import initial_dictionary, records
from src.etape2_comprendre.colonnes import proposer_roles
from src.etape2_comprendre.diagnostic import diagnose
from src.etape3_corriger.pipeline import pipeline
from src.etape3_corriger.points import (decisions, detecter_points, motif_lisible, phrases_journal,
                                        plan_nettoyage, resume_resultat)

EXEMPLE = Path(__file__).parents[1] / "fixtures" / "exemple.csv"


def charger():
    raw = pd.read_csv(EXEMPLE, dtype={"id": "string"}, keep_default_na=False, na_values=[""])
    dictionary = records(initial_dictionary(raw))
    diagnostic = diagnose(raw, dictionary, ignore_markers=True)
    proposer_roles(dictionary, diagnostic["numeric_hints"])
    return raw, dictionary, diagnostic


def nettoyer(raw, dictionary, choix, diagnostic):
    plan = plan_nettoyage(dictionary, choix, diagnostic["suspects"])
    cleaned, rejects, log = pipeline(raw, plan["dictionary"], [], plan["missing_rules"], deduplicate=plan["deduplicate"],
                                     conversion_policies=plan["conversion_policies"])
    return plan, cleaned, rejects, log


def options(points, type_, cle):
    ligne = next(l for p in points if p["type"] == type_ for l in p["lignes"] if l["cle"] == cle)
    return [o[0] for o in ligne["options"]], ligne["defaut"]


class DetectionTests(unittest.TestCase):
    def test_four_points_of_the_sample_with_no_change_by_default(self):
        raw, dictionary, diagnostic = charger()
        points = detecter_points(raw, dictionary, {}, diagnostic)
        self.assertEqual([p["type"] for p in points], ["marqueurs", "texte", "vides", "doublons"])
        self.assertEqual(sum(len(p["lignes"]) for p in points), 4)
        self.assertEqual({l["defaut"] for p in points for l in p["lignes"]}, {"garder", "laisser"})
        self.assertIn("ligne 6 = ligne 4", points[3]["lignes"][0]["texte"])

    def test_default_choices_leave_the_data_unchanged(self):
        raw, dictionary, diagnostic = charger()
        original = raw.copy(deep=True)
        _, cleaned, rejects, _ = nettoyer(raw, dictionary, {}, diagnostic)
        assert_frame_equal(cleaned, raw)
        self.assertTrue(rejects.empty)
        assert_frame_equal(raw, original)

    def test_median_only_for_numbers_and_unknown_only_for_categories(self):
        raw, dictionary, diagnostic = charger()
        points = detecter_points(raw, dictionary, {}, diagnostic)
        # montant est encore du texte : ni médiane, ni « Inconnu ».
        self.assertEqual(options(points, "vides", "montant")[0], ["laisser", "ecarter"])
        choix = {"marqueurs": {"?": "manquant"}, "texte": {"montant": "nombres"}}
        points = detecter_points(raw, dictionary, choix, diagnostic)
        self.assertEqual(options(points, "vides", "montant")[0], ["laisser", "mediane", "ecarter"])
        self.assertEqual(options(points, "vides", "categorie")[0], ["laisser", "inconnu", "ecarter"])
        texte = {l["cle"]: l["texte"] for p in points if p["type"] == "vides" for l in p["lignes"]}
        self.assertIn("2 cases vides", texte["montant"])

    def test_markers_are_grouped_by_code_across_columns(self):
        raw = pd.DataFrame({"a": ["?", "x", "?"], "b": ["1", "?", "NA"]})
        dictionary = records(initial_dictionary(raw))
        diagnostic = diagnose(raw, dictionary, ignore_markers=True)
        lignes = detecter_points(raw, dictionary, {}, diagnostic)[0]["lignes"]
        self.assertEqual([l["cle"] for l in lignes], ["?", "NA"])
        self.assertIn("3 cases dans 2 colonnes", lignes[0]["texte"])

    def test_ambiguous_dates_default_to_the_reading_without_errors(self):
        raw = pd.DataFrame({"date_vente": ["05/03/2026", "29/02/2024", "01/12/2025"]})
        dictionary = records(initial_dictionary(raw))
        points = detecter_points(raw, dictionary, {}, diagnose(raw, dictionary, ignore_markers=True))
        self.assertEqual(points[0]["type"], "dates")
        self.assertEqual(points[0]["lignes"][0]["defaut"], "jour")
        iso = pd.DataFrame({"date_vente": ["2026-03-05", "2024-02-29"]})
        dico_iso = records(initial_dictionary(iso))
        self.assertEqual(detecter_points(iso, dico_iso, {}, diagnose(iso, dico_iso, ignore_markers=True)), [])


class ChoixTests(unittest.TestCase):
    def test_mockup_scenario(self):
        raw, dictionary, diagnostic = charger()
        choix = {"marqueurs": {"?": "manquant"}, "texte": {"montant": "nombres"}, "vides": {"montant": "laisser"},
                 "doublons": {"doublons": "garder"}}
        plan, cleaned, rejects, log = nettoyer(raw, dictionary, choix, diagnostic)
        self.assertEqual(cleaned["categorie"].isna().sum(), 2)
        self.assertEqual(cleaned["montant"].isna().sum(), 2)
        resultat = resume_resultat(raw, plan, cleaned, rejects)
        self.assertEqual((resultat["gardees"], resultat["ecartees"]), (7, 0))
        self.assertEqual(resultat["moyennes"][0]["colonne"], "montant")
        self.assertAlmostEqual(resultat["moyennes"][0]["apres"], 18.1)
        self.assertIn("montant : 1 texte devenu une case vide", phrases_journal(log))

    def test_excluded_lines_keep_reference_and_readable_reason(self):
        raw, dictionary, diagnostic = charger()
        choix = {"texte": {"montant": "ecarter"}, "doublons": {"doublons": "une"}}
        plan, cleaned, rejects, log = nettoyer(raw, dictionary, choix, diagnostic)
        self.assertEqual(rejects[("Traçabilité", "Enregistrement source")].tolist(), [3, 6])
        self.assertEqual(rejects[("Donnée source", "montant")].tolist(), ["abc", "15"])
        resultat = resume_resultat(raw, plan, cleaned, rejects)
        self.assertEqual((resultat["gardees"], resultat["ecartees"]), (5, 2))
        self.assertEqual(dict(resultat["motifs"]), {"montant : texte au lieu d'un nombre": 1,
                                                    "copie identique d'une autre ligne": 1})

    def test_plan_does_not_modify_the_session_dictionary(self):
        raw, dictionary, diagnostic = charger()
        before = [dict(d) for d in dictionary]
        plan_nettoyage(dictionary, {"marqueurs": {"?": "manquant"}, "texte": {"montant": "nombres"}}, diagnostic["suspects"])
        self.assertEqual(dictionary, before)

    def test_decisions_and_readable_reasons(self):
        raw, dictionary, diagnostic = charger()
        points = detecter_points(raw, dictionary, {}, diagnostic)
        lignes = decisions(points, {"doublons": {"doublons": "une"}})
        self.assertEqual(lignes[-1]["choix"], "Garder une seule ligne")
        self.assertEqual(lignes[0]["choix"], "Garder tel quel")
        self.assertEqual(motif_lisible("Valeur manquante : montant"), "montant vide")
        self.assertEqual(phrases_journal([]), ["Aucun changement : les données restent telles qu'importées."])


if __name__ == "__main__":
    unittest.main()
