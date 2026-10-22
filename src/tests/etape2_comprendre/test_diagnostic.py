import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.core.dictionnaire import initial_dictionary, records
from src.etape2_comprendre.diagnostic import diagnose


class DiagnosticTests(unittest.TestCase):
    def test_counts_statistics_and_suspects_are_separate(self):
        data = pd.DataFrame({"value": [1., None, 3.], "code": ["?", "A", "NA"]})
        original = data.copy(deep=True)
        result = diagnose(data, records(initial_dictionary(data)))
        value = result["columns"].set_index("Colonne").loc["value"]
        self.assertEqual(value["Vides détectés"], 1)
        self.assertEqual(value["Vides (%)"], 33.33)
        self.assertEqual(value["Moyenne"], 2.)
        self.assertEqual(value["Médiane"], 2.)
        self.assertEqual(result["suspects"].Occurrences.sum(), 2)
        self.assertEqual(result["normalized"].code.tolist(), ["?", "A", "NA"])
        assert_frame_equal(data, original)

    def test_conversion_errors_are_distinguished_from_existing_blanks(self):
        data = pd.DataFrame({"value": ["1", "bad", None]})
        dictionary = records(initial_dictionary(data))
        dictionary[0].update({"Type attendu": "Nombre", "Rôle": "Mesure"})
        summary = diagnose(data, dictionary)["columns"].iloc[0]
        self.assertEqual(summary["Vides détectés"], 1)
        self.assertEqual(summary["Conversions impossibles"], 1)
        self.assertEqual(summary["Vides après conversion"], 2)

    def test_mostly_numeric_text_is_reported_without_changing_type(self):
        data = pd.DataFrame({"montant": ["10.5", "20", "abc", None, "15"], "id": ["1", "x", "3", "4", "5"],
                             "texte": ["a", "b", "1", "c", "d"]})
        dictionary = records(initial_dictionary(data))
        dictionary[1]["Rôle"] = "Identifiant"
        result = diagnose(data, dictionary)
        hints = result["numeric_hints"]
        self.assertEqual(hints.Colonne.tolist(), ["montant"])
        self.assertEqual(hints.iloc[0]["Valeurs non numériques"], 1)
        self.assertEqual(hints.iloc[0]["Exemples non numériques"], "abc")
        self.assertEqual(result["prepared"].montant.tolist()[2], "abc")
        dictionary[0]["Type attendu"] = "Nombre"
        self.assertTrue(diagnose(data, dictionary)["numeric_hints"].empty)

    def test_markers_can_be_left_out_of_text_in_numbers(self):
        data = pd.DataFrame({"x": ["1", "2", "3", "4", "?", "abc"]})
        dictionary = records(initial_dictionary(data))
        self.assertEqual(diagnose(data, dictionary)["numeric_hints"].iloc[0]["Valeurs non numériques"], 2)
        hints = diagnose(data, dictionary, ignore_markers=True)["numeric_hints"]
        self.assertEqual((hints.iloc[0]["Valeurs non numériques"], hints.iloc[0]["Exemples non numériques"]), (1, "abc"))
