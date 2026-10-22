import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.dictionnaire import initial_dictionary, records
from src.core.regles import audit, compare_audits, recommendation
from src.etape3_corriger.pipeline import pipeline


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.DataFrame({"id": ["001", "001", "003", "004"],
                                 "hours": ["1", "3", "?", "bad"],
                                 "start": ["2026-01-01"]*4,
                                 "end": ["2026-01-02", "2025-12-31", None, "not a date"]})
        self.dictionary = records(initial_dictionary(self.raw))
        self.dictionary[0].update(Obligatoire=True, Unique=True, Critique=True)
        self.dictionary[1].update({"Type attendu": "Nombre", "Rôle": "Mesure", "Marqueurs vides": "?"})
        self.dictionary[2]["Type attendu"] = "Date"
        self.dictionary[3]["Type attendu"] = "Date"

    def test_audit_explains_violations_and_preserves_source(self):
        original = self.raw.copy(deep=True)
        rules = [{"id": "dates", "column": "end", "other": "start", "kind": "Ordre des dates", "priority": "P1", "threshold": 0.}]
        summary, details = audit(self.raw, self.dictionary, rules)
        self.assertEqual(summary.loc[summary["Règle"] == "Unique", "Anomalies"].iloc[0], 2)
        self.assertEqual(summary.loc[summary.ID == "dates", "Anomalies"].iloc[0], 2)
        self.assertEqual(details.loc[details["ID règle"] == "dates", "Enregistrement source"].tolist(), [2, 4])
        assert_frame_equal(self.raw, original)

    def test_invalid_conversion_blocks_by_default(self):
        with self.assertRaises(ValueError):
            pipeline(self.raw, self.dictionary, [], {})

    def test_conversion_rejects_and_imputation_are_traceable(self):
        result, rejects, log = pipeline(self.raw, self.dictionary, [], {"hours": "Moyenne"},
                                        conversion_policy="Mettre en rejet", justification="Analyse", owner="Analyste")
        self.assertEqual(result.hours.tolist(), [1., 3., 2.])
        self.assertEqual(result.id.iloc[0], "001")
        self.assertEqual(rejects[("Traçabilité", "Enregistrement source")].tolist(), [4])
        self.assertIn("bad", rejects[("Donnée source", "hours")].tolist())
        self.assertTrue(all(r["Date UTC"] and r["Justification"] == "Analyse" for r in log))

    def test_rejected_values_do_not_influence_mean(self):
        raw = pd.DataFrame({"x": [1., 1000., None]})
        dictionary = records(initial_dictionary(raw))
        rule = {"id": "range", "column": "x", "kind": "Intervalle", "low": 0., "high": 10., "threshold": 0., "priority": "P1"}
        result, rejects, _ = pipeline(raw, dictionary, [rule], {"x": "Moyenne"}, reject_rule_ids=["range"])
        self.assertEqual(result.x.tolist(), [1., 1.])
        self.assertEqual(len(rejects), 1)

    def test_duplicate_and_missing_rejections_account_for_all_rows(self):
        raw = pd.DataFrame({"id": ["01", "01", None], "x": [1, 1, 2]})
        dictionary = records(initial_dictionary(raw))
        result, rejects, _ = pipeline(raw, dictionary, [], {"id": "Supprimer les lignes"}, deduplicate=True)
        self.assertEqual(len(result)+len(rejects), len(raw))
        self.assertEqual(set(rejects[("Traçabilité", "Enregistrement source")]), {2, 3})

    def test_recommendation_depends_on_defined_controls(self):
        empty, _ = audit(self.raw, records(initial_dictionary(self.raw)), [])
        self.assertEqual(recommendation(empty, 4)[0], "À évaluer")
        summary, _ = audit(self.raw, self.dictionary, [])
        self.assertEqual(recommendation(summary, 4)[0], "NO-GO")
        self.assertEqual(recommendation(empty, 0)[0], "NO-GO")

    def test_date_format_and_trim_are_applied_to_exported_data(self):
        raw = pd.DataFrame({"date": [" 31/12/2026 "]})
        dictionary = records(initial_dictionary(raw))
        dictionary[0].update({"Type attendu": "Date", "Format date": "%d/%m/%Y"})
        result, _, _ = pipeline(raw, dictionary, [], {}, trim=True)
        self.assertEqual(result.date.iloc[0], pd.Timestamp("2026-12-31"))
        summary, _ = audit(result, dictionary, [])
        self.assertEqual(summary.iloc[0]["Statut"], "Conforme")


class ComparisonTests(unittest.TestCase):
    def test_exclusions_are_not_counted_as_corrections(self):
        raw = pd.DataFrame({"id": ["1", "2", "2", "3", "4"], "groupe": ["a", None, "b", None, "c"],
                            "valeur": [1., None, 3., 4., 5.]})
        dictionary = records(initial_dictionary(raw))
        rules = [{"id": "U", "column": "id", "kind": "Unique", "priority": "P1", "threshold": 0.},
                 {"id": "G", "column": "groupe", "kind": "Obligatoire", "priority": "P2", "threshold": 0.},
                 {"id": "V", "column": "valeur", "kind": "Obligatoire", "priority": "P3", "threshold": 25.}]
        cleaned, _, _ = pipeline(raw, dictionary, rules, {"groupe": "Supprimer les lignes", "valeur": "Médiane"},
                                 reject_rule_ids=["U"])
        before, before_details = audit(raw, dictionary, rules)
        after, after_details = audit(cleaned, dictionary, rules)
        result = compare_audits(before, before_details, after, after_details, cleaned.index).set_index("ID")
        # Unicité : les deux occurrences de « 2 » sont mises en rejet, rien n'est corrigé.
        self.assertEqual(result.loc["U", ["Anomalies avant", "Anomalies après"]].tolist(), [2, 0])
        self.assertEqual(result.loc["U", "Écartées par exclusion de lignes"], 2)
        self.assertEqual(result.loc["U", "Résolues sur lignes conservées"], 0)
        # Complétude du groupe : lignes supprimées, donc exclusion.
        self.assertEqual(result.loc["G", "Écartées par exclusion de lignes"], 2)
        # Valeur manquante sur la ligne 2 (rejetée) : exclusion, pas de remplacement.
        self.assertEqual(result.loc["V", "Écartées par exclusion de lignes"], 1)
        self.assertEqual(result.loc["V", "Statut avant"], "Conforme")
        self.assertTrue((result["Nouvelles anomalies"] == 0).all())

    def test_imputation_is_a_resolution_on_kept_rows(self):
        raw = pd.DataFrame({"valeur": [1., None, 3.]})
        dictionary = records(initial_dictionary(raw))
        rules = [{"id": "V", "column": "valeur", "kind": "Obligatoire", "priority": "P2", "threshold": 0.}]
        cleaned, _, _ = pipeline(raw, dictionary, rules, {"valeur": "Médiane"})
        before, before_details = audit(raw, dictionary, rules)
        after, after_details = audit(cleaned, dictionary, rules)
        row = compare_audits(before, before_details, after, after_details, cleaned.index).iloc[0]
        self.assertEqual((row["Écartées par exclusion de lignes"], row["Résolues sur lignes conservées"]), (0, 1))
        self.assertEqual(row["Statut après"], "Conforme")
