import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.dictionnaire import initial_dictionary, records
from src.core.regles import audit
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

    def test_date_format_and_trim_are_applied_to_exported_data(self):
        raw = pd.DataFrame({"date": [" 31/12/2026 "]})
        dictionary = records(initial_dictionary(raw))
        dictionary[0].update({"Type attendu": "Date", "Format date": "%d/%m/%Y"})
        result, _, _ = pipeline(raw, dictionary, [], {}, trim=True)
        self.assertEqual(result.date.iloc[0], pd.Timestamp("2026-12-31"))
        summary, _ = audit(result, dictionary, [])
        self.assertEqual(summary.iloc[0]["Statut"], "Conforme")
