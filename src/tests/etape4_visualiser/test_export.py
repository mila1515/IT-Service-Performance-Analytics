import io
import json
import unittest
import zipfile

import pandas as pd

from src.core.dictionnaire import initial_dictionary, records
from src.etape3_corriger.pipeline import pipeline
from src.etape4_visualiser.export import archive_projet, rejets_lisibles

SOURCE = b"id,Raison,valeur\n001,x,4\n001,x,4\n002,y,abc\n"


def nettoyer():
    raw = pd.read_csv(io.BytesIO(SOURCE), dtype={"id": "string"}, keep_default_na=False, na_values=[""])
    dictionary = records(initial_dictionary(raw))
    dictionary[2]["Type attendu"] = "Nombre"
    cleaned, rejects, log = pipeline(raw, dictionary, [], {}, deduplicate=True,
                                     conversion_policies={"valeur": "Mettre en rejet"})
    return raw, dictionary, cleaned, rejects, log


class ExportTests(unittest.TestCase):
    def test_rejects_have_one_header_line_and_readable_reasons(self):
        _, _, _, rejects, _ = nettoyer()
        lisibles = rejets_lisibles(rejects)
        self.assertEqual(lisibles.columns.tolist(), ["Ligne d'origine", "Raison", "id", "Raison (donnée)", "valeur"])
        self.assertEqual(lisibles["Ligne d'origine"].tolist(), [2, 3])
        self.assertEqual(lisibles["Raison"].tolist(), ["copie identique d'une autre ligne", "valeur : texte au lieu d'un nombre"])
        self.assertEqual(lisibles["id"].tolist(), ["001", "002"])

    def test_archive_keeps_the_original_file_unchanged(self):
        _, dictionary, cleaned, rejects, log = nettoyer()
        contenu = archive_projet(SOURCE, "donnees.csv", cleaned, rejects, "# Rapport", {"doublons": {"doublons": "une"}}, log, dictionary)
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            self.assertEqual(sorted(archive.namelist()), ["LISEZMOI.txt", "donnees_corrigees.csv", "fichier_origine/donnees.csv",
                                                          "journal.json", "lignes_ecartees.csv", "rapport_qualite.md"])
            self.assertEqual(archive.read("fichier_origine/donnees.csv"), SOURCE)
            self.assertIn("001", archive.read("donnees_corrigees.csv").decode("utf-8-sig"))
            self.assertEqual(json.loads(archive.read("journal.json"))["choix"], {"doublons": {"doublons": "une"}})


if __name__ == "__main__":
    unittest.main()
