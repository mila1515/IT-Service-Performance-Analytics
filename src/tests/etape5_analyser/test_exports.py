"""Dossier « données + notebook » : contenu du ZIP ; le notebook s'exécute vraiment dans le dossier extrait."""
import importlib.util
import io
import json
import os
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

import pandas as pd

from src.core.lecture import lire_avec_identifiants
from src.etape2_comprendre.colonnes import dictionnaire_propose
from src.etape4_visualiser.preparation import prepare
from src.etape5_analyser.calculs import duree
from src.etape5_analyser.exports import export_donnees, nom_colonne_delai, notebook

FIXTURES = Path(__file__).parents[1] / "fixtures"
REGLAGES = {"identifiant": "ref_commande", "groupe": "magasin", "statistique": "mediane", "mesure": "montant_ttc",
            "debut": "date_commande", "fin": "date_livraison", "unite_temps": "jours", "date": "date_commande"}
MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


def ventes():
    raw, _ = lire_avec_identifiants((FIXTURES / "ventes.csv").read_bytes())
    roles = {d["Colonne"]: d["Rôle"] for d in dictionnaire_propose(raw)}
    return prepare(raw, roles, True)[0], roles


def executer_notebook(export):
    """Extrait le ZIP et exécute les cellules de code du notebook dans ce dossier, comme Jupyter le ferait.

    Sans matplotlib, les cellules étiquetées « graphique » sont sautées.
    """
    with tempfile.TemporaryDirectory() as dossier, zipfile.ZipFile(io.BytesIO(export)) as archive:
        archive.extractall(dossier)
        cellules = json.loads(Path(dossier, "analyse.ipynb").read_text(encoding="utf-8"))["cells"]
        avant = os.getcwd()
        os.environ.setdefault("MPLBACKEND", "Agg")
        os.chdir(dossier)
        try:
            with warnings.catch_warnings():
                # Mode sans écran des tests : plt.show() ne peut rien afficher.
                warnings.simplefilter("ignore", UserWarning)
                espace = {}
                for cellule in cellules:
                    graphique = "graphique" in cellule["metadata"].get("tags", [])
                    if cellule["cell_type"] == "code" and (MATPLOTLIB or not graphique):
                        exec(cellule["source"], espace)
        finally:
            os.chdir(avant)
        return espace


class ExportsTests(unittest.TestCase):
    def test_one_folder_with_data_delay_dictionary_notebook_and_instructions(self):
        data, roles = ventes()
        colonne = nom_colonne_delai("date_commande", "date_livraison", "jours")
        contenu = export_donnees(data, roles, "ventes.csv", REGLAGES, (colonne, duree(data, "date_commande", "date_livraison")))
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            self.assertEqual(sorted(archive.namelist()),
                             ["LISEZMOI.txt", "analyse.ipynb", "dictionnaire_colonnes.csv", "donnees_corrigees.csv"])
            donnees = pd.read_csv(archive.open("donnees_corrigees.csv"), dtype={"ref_commande": "string"})
            dictionnaire = pd.read_csv(archive.open("dictionnaire_colonnes.csv"))
            lisezmoi = archive.read("LISEZMOI.txt").decode("utf-8")
        self.assertEqual(len(donnees), 60)
        self.assertTrue((donnees[colonne] >= 1).all())
        self.assertEqual(dictionnaire["Colonne"].tolist()[-1], colonne)
        self.assertIn("Identifiant", dictionnaire["Type"].tolist())
        self.assertIn("Extraire tout", lisezmoi)

    def test_notebook_walks_through_every_step_then_the_analyses(self):
        data, roles = ventes()
        titres = [c["source"].splitlines()[0] for c in notebook("ventes.csv", roles, REGLAGES)["cells"] if c["cell_type"] == "markdown"]
        for attendu in ["## 1. Charger les données", "## 2. Aperçu", "## 3. Qualité", "## 4. Statistiques", "## 5. Graphiques",
                        "## 6. Analyses de l'étape Analyser", "### Comparer des groupes", "### Mesurer un délai"]:
            self.assertIn(attendu, titres)

    def test_notebook_runs_in_the_extracted_folder(self):
        data, roles = ventes()
        export = export_donnees(data, roles, "ventes.csv", REGLAGES)
        with zipfile.ZipFile(io.BytesIO(export)) as archive:
            self.assertNotIn(b"CMD000", archive.read("analyse.ipynb"))  # le notebook lit le CSV, il ne le recopie pas
        espace = executer_notebook(export)
        self.assertEqual(len(espace["donnees"]), 60)
        self.assertEqual(espace["qualite"].loc["montant_ttc", "cases vides"], 0)
        self.assertEqual(len(espace["unites"]), 60)
        self.assertEqual(espace["delais"]["count"].sum(), 60)

    def test_column_names_are_data_never_code(self):
        nom = "x'); import os; os.remove('a') #"
        data = pd.DataFrame({nom: ["A", "B", "A"], "n": [1.0, 2.0, 3.0]}).astype({nom: "string"})
        roles = {nom: "Catégorie", "n": "Mesure"}
        reglages = {"groupe": nom, "statistique": "moyenne", "mesure": "n"}
        cellules = notebook("f.csv", roles, reglages)["cells"]
        self.assertTrue(any(repr(nom) in c["source"] for c in cellules if c["cell_type"] == "code"))
        espace = executer_notebook(export_donnees(data, roles, "f.csv", reglages))
        self.assertEqual(espace["comparaison"].loc["A", "mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
