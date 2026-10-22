"""Parcours simple en 4 étapes, piloté avec AppTest (sans navigateur)."""
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app.py")
EXEMPLE = Path(__file__).parent / "fixtures" / "exemple.csv"


def fichier(contenu, nom="donnees.csv"):
    upload = io.BytesIO(contenu)
    upload.name = nom
    return upload


def bouton(app, debut):
    return next(b for b in app.button if b.label.startswith(debut))


def textes(elements):
    return " ".join(str(e.value) for e in elements)


class ParcoursSimpleTests(unittest.TestCase):
    def ouvrir(self, contenu=None):
        app = AppTest.from_file(APP, default_timeout=60)
        self.upload = patch("streamlit.file_uploader", return_value=fichier(contenu or EXEMPLE.read_bytes(), "exemple.csv"))
        self.upload.start()
        self.addCleanup(self.upload.stop)
        return app.run()

    def test_import_shows_the_file_without_any_required_input(self):
        app = self.ouvrir()
        self.assertFalse(app.exception)
        self.assertIn("7 lignes et 4 colonnes", textes(app.success))
        apercu = app.dataframe[0].value
        self.assertEqual(apercu["id"].tolist()[:2], ["001", "002"])
        self.assertNotIn("None", apercu.astype(str).to_numpy().ravel().tolist())
        self.assertFalse(app.text_input)
        self.assertFalse(app.text_area)

    def test_wrong_separator_is_explained_and_fixed(self):
        app = self.ouvrir(b"a;b\n1;x\n2;y\n")
        self.assertIn("seule colonne", textes(app.warning))
        self.assertTrue(bouton(app, "Étape suivante").disabled)
        app.segmented_control(key="w_lecture_separateur").set_value(";").run()
        self.assertFalse(app.exception)
        self.assertIn("2 lignes et 2 colonnes", textes(app.success))

    def test_understand_lists_the_points_and_roles_can_be_changed(self):
        app = self.ouvrir()
        bouton(app, "Étape suivante").click().run()
        self.assertEqual(app.session_state.etape, "Comprendre")
        self.assertEqual(next(m.value for m in app.metric if m.label == "Points à vérifier"), "4")
        self.assertIn("ligne 6 = ligne 4", textes(app.markdown))
        app.selectbox(key="w_role_1").set_value("des identifiants").run()
        self.assertEqual(app.session_state.dictionary[1]["Rôle"], "Identifiant")
        self.assertFalse(app.exception)

    def test_default_choices_change_nothing(self):
        app = self.ouvrir()
        app.session_state["etape"] = "Corriger"
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("Aucun changement", textes(app.markdown))
        bouton(app, "Valider et voir les graphiques").click().run()
        self.assertEqual(app.session_state.etape, "Visualiser")
        assert_frame_equal(app.session_state.validation["cleaned"], app.session_state.raw)
        self.assertTrue(app.session_state.validation["rejects"].empty)

    def test_choices_update_the_result_and_exclusion_is_not_correction(self):
        app = self.ouvrir()
        app.session_state["etape"] = "Corriger"
        app.run()
        cles = {c.label: c.key for c in app.segmented_control}
        app.segmented_control(key=cles["« ? » : 2 cases dans 1 colonne (categorie)"]).set_value("manquant").run()
        self.assertIn("categorie : 2 cases vides", textes(app.markdown))
        cle_doublons = next(c.key for c in app.segmented_control if c.label.startswith("1 ligne identique"))
        app.segmented_control(key=cle_doublons).set_value("une").run()
        self.assertFalse(app.exception)
        self.assertEqual(next(m.value for m in app.metric if m.label == "Lignes gardées"), "6 / 7")
        self.assertIn("parce que sa ligne est écartée n'a pas été réparé", textes(app.warning))
        self.assertIn("copie identique d'une autre ligne", textes(app.warning))
        bouton(app, "Valider et voir les graphiques").click().run()
        self.assertEqual(len(app.session_state.validation["rejects"]), 1)
        self.assertEqual(app.session_state.validation["choix"]["marqueurs"], {"?": "manquant"})

    def test_visualise_shows_control_charts_and_downloads(self):
        app = self.ouvrir()
        app.session_state["etape"] = "Visualiser"
        app.run()
        self.assertIn("Validez d'abord vos corrections", textes(app.info))
        app.session_state["etape"] = "Corriger"
        app.run()
        bouton(app, "Valider et voir les graphiques").click().run()
        self.assertFalse(app.exception)
        self.assertIn("À retenir", textes(app.markdown))
        self.assertIn("1 texte ignoré", textes(app.caption))
        self.assertEqual(len(app.get("download_button")), 4)
        app.segmented_control(key="w_ajout_question").set_value("repartition").run()
        bouton(app, "Ajouter ce graphique").click().run()
        self.assertEqual(len(app.session_state.graphiques_ajoutes), 1)
        self.assertFalse(app.exception)

    def test_changing_read_options_after_choices_is_announced(self):
        app = self.ouvrir()
        app.session_state["choix"] = {"doublons": {"doublons": "une"}}
        app.run()
        app.segmented_control(key="w_lecture_decimale").set_value(",").run()
        self.assertIn("vos choix ont été effacés", textes(app.warning))
        self.assertEqual(app.session_state.choix, {})


if __name__ == "__main__":
    unittest.main()
