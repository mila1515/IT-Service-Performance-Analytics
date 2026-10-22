import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.dictionnaire import initial_dictionary, normalize_missing, records
from src.core.regles import audit, validate_rule
from src.etape3_corriger.pipeline import pipeline
from src.expert.repetitions import inspect_repetitions


class RepetitionTests(unittest.TestCase):
    def test_distinct_details_duplicates_and_conflicts(self):
        data = pd.DataFrame({"entity": ["A", "A", "B", "B", "C", "C"],
                             "detail": ["x", "y", "x", "x", "z", "z"],
                             "value": [1, 2, 3, 3, 4, 5]})
        before = data.copy(deep=True)
        result = inspect_repetitions(data, ["entity"], ["detail"])
        summary = result["summary"]
        self.assertEqual(summary["Lecture proposée"].tolist(), ["Lignes distinctes selon le détail choisi", "Doublons stricts potentiels", "Même clé de ligne — valeurs différentes"])
        self.assertEqual(summary["Doublons stricts en excès"].tolist(), [0, 1, 0])
        self.assertEqual(result["differences"].Colonne.tolist(), ["value"])
        assert_frame_equal(data, before)

    def test_rail_keys_and_hr_keys_are_generic(self):
        rail = pd.DataFrame({"train": [42, 42, 42], "date": ["2026-01-01", "2026-01-01", "2026-01-02"],
                             "stop": ["A", "B", "A"], "delay": [1, 3, 5]})
        result = inspect_repetitions(rail, ["train", "date"], ["stop"])
        self.assertEqual(len(result["summary"]), 1)
        self.assertEqual(result["summary"].iloc[0]["Clés de ligne répétées"], 0)
        hr = rail.rename(columns={"train": "employee", "date": "period", "stop": "affectation", "delay": "hours"})
        other = inspect_repetitions(hr, ["employee", "period"], ["affectation"])
        self.assertEqual(other["summary"]["Lecture proposée"].tolist(), result["summary"]["Lecture proposée"].tolist())

    def test_missing_keys_and_details_are_not_assumed_duplicates(self):
        data = pd.DataFrame({"id": [None, None, "A", "A"], "part": [1, 1, None, 2]})
        result = inspect_repetitions(data, ["id"], ["part"])
        self.assertEqual(result["incomplete"], [1, 2])
        self.assertEqual(result["summary"].iloc[0]["Détails incomplets"], 1)
        self.assertEqual(result["summary"].iloc[0]["Lecture proposée"], "Détail incomplet — à investiguer")

    def test_ignored_metadata_does_not_create_false_conflict(self):
        data = pd.DataFrame({"id": ["a", "a"], "value": [1, 1], "load_time": ["x", "y"]})
        result = inspect_repetitions(data, ["id"], compare_columns=["value"])
        self.assertEqual(result["summary"].iloc[0]["Groupes avec différences"], 0)
        self.assertEqual(result["summary"].iloc[0]["Doublons stricts en excès"], 0)

    def test_normalized_markers_are_not_strict_source_duplicates(self):
        raw = pd.DataFrame({"id": ["a", "a"], "value": ["NA", "?"]})
        dictionary = records(initial_dictionary(raw))
        dictionary[1]["Marqueurs vides"] = "NA\n?"
        result = inspect_repetitions(normalize_missing(raw, dictionary), ["id"], source=raw)
        self.assertEqual(result["summary"].iloc[0]["Doublons stricts en excès"], 0)

    def test_composite_control_is_opt_in_and_replays_after_cleaning(self):
        raw = pd.DataFrame({"id": ["a", "a", "a", None], "line": [1, 2, 2, 1], "value": [1, 2, 3, 4]})
        dictionary = records(initial_dictionary(raw))
        before, _ = audit(raw, dictionary, [])
        self.assertTrue(before.empty)
        rule = {"id": "key", "column": "id", "columns": ["id", "line"], "kind": "Clé composée unique", "priority": "P1", "threshold": 0.}
        validate_rule(rule, raw.columns)
        summary, details = audit(raw, dictionary, [rule])
        self.assertEqual(summary.iloc[0]["Anomalies"], 2)
        self.assertEqual(details["Enregistrement source"].tolist(), [2, 3])
        cleaned, rejects, _ = pipeline(raw, dictionary, [rule], {}, reject_rule_ids=["key"])
        self.assertEqual(len(rejects), 2)
        after, _ = audit(cleaned, dictionary, [rule])
        self.assertEqual(after.iloc[0]["Anomalies"], 0)

    def test_empty_result_and_invalid_keys(self):
        data = pd.DataFrame({"id": [1, 2]})
        self.assertTrue(inspect_repetitions(data, ["id"])["summary"].empty)
        for keys, details in [([], []), (["missing"], []), (["id"], ["id"])]:
            with self.assertRaises(ValueError):
                inspect_repetitions(data, keys, details)
