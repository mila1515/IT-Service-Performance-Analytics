"""Passerelles Power BI et Jupyter : contenu des archives ; le notebook généré s'exécute vraiment."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from src.core.lecture import lire_avec_identifiants
from src.etape2_comprendre.colonnes import dictionnaire_propose
from src.etape4_visualiser.preparation import prepare
from src.etape5_analyser.calculs import duree
from src.etape5_analyser.exports import export_jupyter, export_power_bi, nom_colonne_delai, notebook

FIXTURES = Path(__file__).parents[1] / "fixtures"
REGLAGES = {"identifiant": "ref_commande", "groupe": "magasin", "statistique": "mediane", "mesure": "montant_ttc",
            "debut": "date_commande", "fin": "date_livraison", "unite_temps": "jours", "date": "date_commande"}


def ventes():
    raw, _ = lire_avec_identifiants((FIXTURES / "ventes.csv").read_bytes())
    roles = {d["Colonne"]: d["Rôle"] for d in dictionnaire_propose(raw)}
    return prepare(raw, roles, True)[0], roles


def executer_notebook(contenu_zip):
    """Exécute les cellules de code du notebook dans un dossier temporaire, comme Jupyter le ferait."""
    with tempfile.TemporaryDirectory() as dossier, zipfile.ZipFile(io.BytesIO(contenu_zip)) as archive:
        archive.extractall(dossier)
        cellules = json.loads(Path(dossier, "analyse.ipynb").read_text(encoding="utf-8"))["cells"]
        avant = os.getcwd()
        os.chdir(dossier)
        try:
            espace = {}
            for cellule in cellules:
                if cellule["cell_type"] == "code":
                    exec(cellule["source"], espace)
        finally:
            os.chdir(avant)
        return espace


class ExportsTests(unittest.TestCase):
    def test_power_bi_archive_has_data_with_delay_and_a_dictionary(self):
        data, roles = ventes()
        colonne = nom_colonne_delai("date_commande", "date_livraison", "jours")
        contenu = export_power_bi(data, roles, (colonne, duree(data, "date_commande", "date_livraison")))
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            self.assertEqual(sorted(archive.namelist()), ["LISEZMOI.txt", "dictionnaire_colonnes.csv", "donnees_corrigees.csv"])
            donnees = pd.read_csv(archive.open("donnees_corrigees.csv"), dtype={"ref_commande": "string"})
            dictionnaire = pd.read_csv(archive.open("dictionnaire_colonnes.csv"))
        self.assertEqual(len(donnees), 60)
        self.assertTrue((donnees[colonne] >= 1).all())
        self.assertEqual(dictionnaire["Colonne"].tolist()[-1], colonne)
        self.assertIn("Identifiant", dictionnaire["Type"].tolist())

    def test_generated_notebook_runs_and_redoes_the_analyses(self):
        data, roles = ventes()
        espace = executer_notebook(export_jupyter(data, roles, "ventes.csv", REGLAGES))
        self.assertEqual(len(espace["unites"]), 60)
        self.assertIn("delai", espace["unites"])
        self.assertEqual(espace["delais"]["count"].sum(), 60)

    def test_column_names_are_data_never_code(self):
        nom = "x'); import os; os.remove('a') #"
        data = pd.DataFrame({nom: ["A", "B", "A"], "n": [1.0, 2.0, 3.0]}).astype({nom: "string"})
        roles = {nom: "Catégorie", "n": "Mesure"}
        reglages = {"groupe": nom, "statistique": "moyenne", "mesure": "n"}
        cellules = notebook("f.csv", roles, reglages)["cells"]
        self.assertTrue(any(repr(nom) in c["source"] for c in cellules if c["cell_type"] == "code"))
        espace = executer_notebook(export_jupyter(data, roles, "f.csv", reglages))
        self.assertEqual(espace["comparaison"].loc["A", "mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
