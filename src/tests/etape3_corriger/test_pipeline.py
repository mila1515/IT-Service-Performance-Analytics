import unittest

import pandas as pd

from src.core.dictionnaire import initial_dictionary, records
from src.etape3_corriger.pipeline import pipeline


class ConversionParColonneTests(unittest.TestCase):
    def test_policy_per_column_overrides_the_global_one(self):
        raw = pd.DataFrame({"a": ["1", "x"], "b": ["2", "y"], "c": ["3", "z"]})
        dictionary = records(initial_dictionary(raw))
        for d in dictionary:
            d["Type attendu"] = "Nombre"
        with self.assertRaises(ValueError):
            pipeline(raw, dictionary, [], {}, conversion_policies={"a": "Convertir en vide", "b": "Mettre en rejet"})
        cleaned, rejects, _ = pipeline(raw, dictionary, [], {}, conversion_policy="Convertir en vide",
                                       conversion_policies={"b": "Mettre en rejet"})
        self.assertEqual(len(rejects), 1)
        self.assertEqual(cleaned["a"].tolist(), [1.])
        with self.assertRaises(ValueError):
            pipeline(raw, dictionary, [], {}, conversion_policies={"a": "Inventée"})


if __name__ == "__main__":
    unittest.main()
