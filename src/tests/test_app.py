import io
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_missing_counts_are_visible_before_targeted_choices(self):
        upload = io.BytesIO(b"group,hours,complete\na,1,yes\na,,yes\nb,3,yes\n")
        upload.name = "missing.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            steps = app.radio(key="workflow_step").options
            next(w for w in app.button if w.label == "Explorer les données").click().run()
            self.assertEqual(app.radio(key="workflow_step").value, steps[1])
            next(w for w in app.button if w.label == "Continuer vers le nettoyage").click().run()
            table = app.dataframe[0].value
            self.assertEqual(table.Colonne.tolist(), ["hours"])
            self.assertEqual(table["Vides détectés"].tolist(), [1])
            self.assertEqual(table["Moyenne"].tolist(), [2.])
            self.assertEqual([w.key for w in app.selectbox if w.key and w.key.startswith("rule_")], ["rule_1"])
            app.selectbox(key="rule_1").set_value("Médiane")
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            self.assertFalse(app.exception)
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            self.assertEqual(app.radio(key="workflow_step").value, steps[3])
            self.assertEqual(app.session_state.cleaned.hours.tolist(), [1., 2., 3.])
            self.assertTrue(app.session_state.config["justification"])

    def test_sample_csv_through_all_steps(self):
        upload = io.BytesIO((Path(__file__).parent / "fixtures" / "exemple.csv").read_bytes())
        upload.name = "exemple.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any("lues comme nombres : id" in w.value for w in app.info))
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[1]).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("montant" in w.value.Colonne.tolist() for w in app.dataframe if "Exemples non numériques" in w.value))
            self.assertTrue(any("exclues des statistiques" in w.value and "id" in w.value for w in app.caption))
            app.radio(key="workflow_step").set_value(steps[2]).run()
            next(w for w in app.button if w.label.startswith("Reconnaître ? comme vide")).click().run()
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            self.assertFalse(app.exception)
            before_after = app.dataframe[0].value
            self.assertEqual(before_after.loc["Cellules manquantes (marqueurs reconnus inclus)"].tolist(), [3, 3])
            self.assertEqual(before_after.loc["Doublons exacts en excès"].tolist(), [1, 1])
            app.radio(key="workflow_step").set_value(steps[4]).run()
            self.assertFalse(app.exception)
            self.assertTrue(any(w.value.startswith("Évaluation des règles : À évaluer") for w in app.info))
            self.assertEqual(app.session_state.viz_roles, {d["Colonne"]: d["Rôle"] for d in app.session_state.dictionary})
            app.radio(key="workflow_step").set_value(steps[5]).run()
            self.assertFalse(app.exception)

    def test_comparison_separates_exclusions_from_corrections(self):
        upload = io.BytesIO((Path(__file__).parent / "fixtures" / "exemple.csv").read_bytes())
        upload.name = "exemple.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[2]).run()
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            self.assertTrue(any("Aucune règle de qualité définie" in w.value for w in app.info))
            app.session_state.dictionary[0]["Unique"] = True
            app.radio(key="workflow_step").set_value(steps[2]).run()
            next(w for w in app.checkbox if w.label == "Supprimer les lignes strictement identiques").check()
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            self.assertFalse(app.exception)
            comparison = next(w.value for w in app.dataframe if "Écartées par exclusion de lignes" in w.value)
            self.assertEqual(comparison[["Anomalies avant", "Anomalies après", "Écartées par exclusion de lignes",
                                        "Résolues sur lignes conservées"]].iloc[0].tolist(), [2, 0, 1, 1])
            self.assertTrue(any("1 anomalies ont disparu parce que leurs lignes ont été écartées" in w.value for w in app.warning))

    def test_changing_read_options_after_work_is_announced(self):
        upload = io.BytesIO(b"id,v\n001,1\n002,2\n")
        upload.name = "ids.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            app.multiselect(key="import_text_columns").set_value(["id"]).run()
            self.assertFalse(app.warning)
            app.session_state.quality_rules = [{"id": "Q-1", "column": "v", "kind": "Obligatoire", "priority": "P2", "threshold": 0.}]
            app.multiselect(key="import_text_columns").set_value([]).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("session réinitialisée" in w.value for w in app.warning))
            self.assertEqual(app.session_state.quality_rules, [])
            app.run()
            self.assertFalse(any("session réinitialisée" in w.value for w in app.warning))

    def test_special_markers_require_explicit_choice(self):
        upload = io.BytesIO(b"group,value\na,?\nb,4\n")
        upload.name = "markers.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[2]).run()
            self.assertFalse(any(w.key == "rule_1" for w in app.selectbox))
            next(w for w in app.button if w.label.startswith("Reconnaître ? comme vide")).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.dataframe[0].value["Vides détectés"].tolist(), [1])
            self.assertTrue(any(w.key == "rule_1" for w in app.selectbox))
            self.assertEqual(app.session_state.dictionary[1]["Marqueurs vides"], "?")

    def test_discovery_precedes_optional_business_notes(self):
        upload = io.BytesIO(b"entity,detail,value\na,x,1\na,y,2\n")
        upload.name = "discovery.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.dataframe)
            self.assertEqual(app.dataframe[0].value.entity.tolist(), ["a", "a"])
            self.assertFalse(app.text_input)
            self.assertFalse(app.text_area)
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[1]).run()
            self.assertFalse(app.exception)
            self.assertFalse(any(w.key == "field_grain" for w in app.text_input))
            app.radio(key="workflow_step").set_value(steps[0]).run()
            self.assertFalse(app.text_input)
            app.radio(key="workflow_step").set_value(steps[1]).run()
            self.assertTrue(app.dataframe)

    def test_repetition_analysis_does_not_change_cleaned_data(self):
        upload = io.BytesIO(b"entity,detail,value\na,x,1\na,y,2\n")
        upload.name = "generic.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[2]).run()
            next(w for w in app.text_area if w.label == "Note sur les traitements (facultatif)").set_value("Conserver les données pour exploration.")
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            original = app.session_state.cleaned.copy(deep=True)
            app.radio(key="workflow_step").set_value(steps[1]).run()
            app.multiselect(key="repeat_keys_input").set_value(["entity"]).run()
            app.multiselect(key="repeat_detail_input").set_value(["detail"]).run()
            next(w for w in app.button if w.label == "Analyser les répétitions").click().run()
            self.assertFalse(app.exception)
            from pandas.testing import assert_frame_equal
            assert_frame_equal(app.session_state.cleaned, original)
            self.assertEqual(app.session_state.quality_rules, [])
            next(w for w in app.checkbox if w.label.startswith("Je confirme que cette combinaison")).check()
            next(w for w in app.button if w.label == "Ajouter le contrôle d'unicité composée").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.quality_rules[0]["columns"], ["entity", "detail"])
            self.assertNotIn("cleaned", app.session_state)
            upload.seek(0)
            with patch("streamlit.file_uploader", return_value=type("Upload", (), {"getvalue": lambda self: b"other\n1\n", "name": "other.csv"})()):
                app.run()
            self.assertFalse(app.exception)
            self.assertNotIn("repetition_config", app.session_state)
            self.assertEqual(app.session_state.quality_rules, [])

    def test_quality_workflow_and_protected_identifiers(self):
        upload = io.BytesIO(b"id,hours\n001,1\n002,NA\n003,bad\n")
        upload.name = "donnees.csv"
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20)
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            app.multiselect(key="import_text_columns").set_value(["id"]).run()
            dictionary = app.session_state.dictionary
            dictionary[0].update(Obligatoire=True, Unique=True)
            dictionary[1].update({"Type attendu": "Nombre", "Rôle": "Mesure", "Marqueurs vides": "NA"})
            app.session_state.dictionary = dictionary
            steps = app.radio(key="workflow_step").options
            app.radio(key="workflow_step").set_value(steps[1]).run()
            self.assertFalse(app.exception)
            app.radio(key="workflow_step").set_value(steps[2]).run()
            next(w for w in app.text_area if w.label == "Note sur les traitements (facultatif)").set_value("Écarter la valeur invalide et conserver les vides.")
            next(w for w in app.selectbox if w.label == "Si une conversion de type échoue").set_value("Mettre en rejet")
            next(w for w in app.button if w.label == "Prévisualiser les traitements").click().run()
            self.assertFalse(app.exception)
            next(w for w in app.button if w.label == "Valider cette prévisualisation").click().run()
            self.assertEqual(app.session_state.cleaned.id.tolist(), ["001", "002"])
            self.assertEqual(len(app.session_state.rejects), 1)
            self.assertEqual(len(app.session_state.cleaning_versions), 1)
            app.radio(key="workflow_step").set_value(steps[3]).run()
            self.assertFalse(app.exception)
            app.radio(key="workflow_step").set_value(steps[5]).run()
            self.assertFalse(app.exception)
            app.radio(key="workflow_step").set_value(steps[1]).run()
            next(w for w in app.button if w.label == "Enregistrer le dictionnaire").click().run()
            self.assertNotIn("cleaned", app.session_state)
            self.assertEqual(len(app.session_state.cleaning_versions), 1)
