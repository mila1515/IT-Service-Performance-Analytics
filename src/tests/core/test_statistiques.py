import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.etape3_corriger.pipeline import clean


class CleaningTests(unittest.TestCase):
    def test_preserves_source_and_index(self):
        raw = pd.DataFrame({"value": [2., None, 4.]}, index=[10, 11, 12])
        original = raw.copy(deep=True)
        result, log = clean(raw, {"value": "Médiane"})
        self.assertEqual(result.value.tolist(), [2., 3., 4.])
        self.assertEqual(result.index.tolist(), [10, 11, 12])
        self.assertEqual(log, [{"Colonne": "value", "Action": "Médiane", "Cellules concernées": 1}])
        assert_frame_equal(raw, original)

    def test_imputation_is_independent_of_rule_order(self):
        raw = pd.DataFrame({"a": [1., 3., None], "b": [None, 1., 2.]})
        first, _ = clean(raw, {"a": "Moyenne", "b": "Médiane"})
        second, _ = clean(raw, {"b": "Médiane", "a": "Moyenne"})
        assert_frame_equal(first, second)
        self.assertEqual(first.a.iloc[-1], 2.)

    def test_all_missing_rejects_imputation(self):
        with self.assertRaises(ValueError):
            clean(pd.DataFrame({"x": [float("nan")]}), {"x": "Médiane"})

    def test_unknown_category_and_row_removal_left_to_pipeline(self):
        result, log = clean(pd.DataFrame({"x": [None, "a"], "y": [1., None]}), {"x": "Inconnu", "y": "Supprimer les lignes"})
        self.assertEqual(result.x.tolist(), ["Inconnu", "a"])
        self.assertEqual(len(result), 2)
        self.assertEqual(len(log), 1)

if __name__ == "__main__":
    unittest.main()
