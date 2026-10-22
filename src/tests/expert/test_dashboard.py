import io
import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

SCRIPT = '''
import pandas as pd
from src.expert.dashboard import dashboard
dashboard(pd.DataFrame({"group": ["a", "a", "b"], "category": ["x", "y", "x"],
                        "hours": [1., 3., 8.], "cost": [2., 5., 7.],
                        "date_ouverture": ["2026-01-01", "2026-02-01", "2026-03-01"]}))
'''


class DashboardTests(unittest.TestCase):
    def widget(self, app, kind, label):
        return next(w for w in getattr(app, kind) if w.label == label)

    def test_build_edit_filter_and_remove(self):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        self.assertFalse(app.exception)
        self.widget(app, "button", "Ajouter au dashboard").click().run()
        self.assertFalse(app.exception)
        self.widget(app, "button", "Ajouter au dashboard").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.viz_charts), 2)
        global_columns = app.multiselect(key="viz_0_global_columns")
        global_columns.set_value(["group"]).run()
        app.multiselect(key="viz_0_global_0_group_values_0").set_value(["a"])
        self.widget(app, "button", "Appliquer les filtres globaux").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.viz_filters[0]["values"], ["a"])
        selected = self.widget(app, "selectbox", "Graphique").value
        self.widget(app, "selectbox", "Largeur").set_value("Pleine")
        self.widget(app, "number_input", "Position (1 = en haut)").set_value(2)
        self.widget(app, "button", "Enregistrer la disposition").click().run()
        self.assertEqual(app.session_state.viz_charts[1]["id"], selected)
        self.assertEqual(app.session_state.viz_charts[1]["width"], "Pleine")
        self.widget(app, "button", "Retirer ce graphique").click().run()
        self.assertEqual(len(app.session_state.viz_charts), 1)
        self.assertFalse(app.exception)

    def test_all_suggested_chart_types_render(self):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        import pandas as pd
        from src.core.roles import infer_roles
        from src.etape4_visualiser.graphiques import suggestions
        roles = infer_roles(pd.DataFrame({"group": ["a"], "category": ["x"], "hours": [1.], "cost": [2.], "date_ouverture": ["2026-01-01"]}))
        seen = set()
        for index, spec in enumerate(suggestions(roles)):
            if spec["kind"] in seen:
                continue
            seen.add(spec["kind"])
            self.widget(app, "selectbox", "Point de départ").set_value(str(index)).run()
            self.assertFalse(app.exception, spec["kind"])
        self.assertEqual(len(seen), 6)

    def test_restore_and_edit_local_filters(self):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        self.widget(app, "button", "Ajouter au dashboard").click().run()
        chart_id = app.session_state.viz_charts[0]["id"]
        self.widget(app, "selectbox", "Point de départ").set_value(f"saved_{chart_id}").run()
        local_columns = next(w for w in app.multiselect if "_local_columns" in w.key)
        local_columns.set_value(["group"]).run()
        next(w for w in app.multiselect if "_local_0_group_values_0" in w.key).set_value(["b"])
        self.widget(app, "button", "Mettre à jour le graphique").click().run()
        self.assertFalse(app.exception)
        charts = app.session_state.viz_charts
        self.assertEqual(charts[0]["filters"][0]["values"], ["b"])
        config = {"version": 1, "roles": app.session_state.viz_roles,
                  "dayfirst": False, "filters": [], "charts": charts}
        upload = io.BytesIO(json.dumps(config).encode())
        with patch("streamlit.file_uploader", return_value=upload):
            app.run()
            self.widget(app, "button", "Restaurer le dashboard").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.viz_revision, 1)
        self.assertEqual(app.session_state.viz_charts[0]["filters"][0]["values"], ["b"])

    def test_display_follows_list_order_and_edit_shortcut(self):
        app = AppTest.from_string(SCRIPT, default_timeout=30).run()
        for index in range(3):
            self.widget(app, "selectbox", "Point de départ").set_value(str(index)).run()
            self.widget(app, "button", "Ajouter au dashboard").click().run()
        titles = [c["title"] for c in app.session_state.viz_charts]
        first = app.session_state.viz_charts[0]["id"]
        self.widget(app, "number_input", "Position (1 = en haut)").set_value(3)
        self.widget(app, "button", "Enregistrer la disposition").click().run()
        expected = titles[1:] + titles[:1]
        self.assertEqual([c["title"] for c in app.session_state.viz_charts], expected)
        self.assertEqual([s.value for s in app.subheader][-3:], expected)
        self.assertNotIn("row", app.session_state.viz_charts[0])
        self.widget(app, "selectbox", "Graphique").set_value(first).run()
        self.widget(app, "button", "Modifier ce graphique").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.widget(app, "selectbox", "Point de départ").value, f"saved_{first}")
        self.assertTrue(any(b.label == "Mettre à jour le graphique" for b in app.button))
        self.widget(app, "button", "Retirer ce graphique").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state.viz_charts), 2)

    def test_legacy_rows_are_converted_to_order(self):
        app = AppTest.from_string(SCRIPT, default_timeout=20).run()
        self.widget(app, "button", "Ajouter au dashboard").click().run()
        self.widget(app, "selectbox", "Point de départ").set_value("1").run()
        self.widget(app, "button", "Ajouter au dashboard").click().run()
        charts = [dict(c, row=row, title=title) for c, row, title in
                  zip(app.session_state.viz_charts, [2, 1], ["deuxième ligne", "première ligne"])]
        config = {"version": 1, "roles": app.session_state.viz_roles, "dayfirst": False, "filters": [], "charts": charts}
        with patch("streamlit.file_uploader", return_value=io.BytesIO(json.dumps(config).encode())):
            app.run()
            self.widget(app, "button", "Restaurer le dashboard").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([c["title"] for c in app.session_state.viz_charts], ["première ligne", "deuxième ligne"])
        self.assertFalse(any("row" in c for c in app.session_state.viz_charts))

    def test_high_cardinality_filters_keep_all_rows_by_default(self):
        script = """
import pandas as pd
from src.expert.dashboard import dashboard
dashboard(pd.DataFrame({"ref": [f"R{i:05d}" for i in range(1200)], "groupe": [f"g{i % 60}" for i in range(1200)],
                        "petit": ["a", "b"] * 600}))
"""
        app = AppTest.from_string(script, default_timeout=30).run()
        app.multiselect(key="viz_0_global_columns").set_value(["ref", "groupe", "petit"]).run()
        self.assertFalse(app.exception)
        modes = {w.key: w.value for w in app.radio}
        self.assertEqual(modes["viz_0_global_0_ref_mode"], "Exclure les valeurs choisies")
        self.assertEqual(modes["viz_0_global_1_groupe_mode"], "Exclure les valeurs choisies")
        self.assertEqual(modes["viz_0_global_2_petit_mode"], "Retenir les valeurs choisies")
        self.assertEqual(app.text_area(key="viz_0_global_0_ref_values_1").value, "")
        self.assertEqual(app.multiselect(key="viz_0_global_1_groupe_values_1").value, [])
        self.assertEqual(app.multiselect(key="viz_0_global_2_petit_values_0").value, ["a", "b"])
        app.text_area(key="viz_0_global_0_ref_values_1").set_value("R00000\nR00001\nabsent")
        self.widget(app, "button", "Appliquer les filtres globaux").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("1,198 / 1,200 lignes retenues" in m.value for m in app.markdown))
        stored = app.session_state.viz_filters[0]
        self.assertEqual((stored["exclude"], stored["values"]), (True, ["R00000", "R00001", "absent"]))
        self.assertTrue(any("1 valeur(s) saisie(s) absente(s)" in c.value for c in app.caption))

    def test_large_histogram_and_box_use_all_values(self):
        script = '''
import pandas as pd
from src.expert.dashboard import dashboard
dashboard(pd.DataFrame({"hours": range(6000)}))
'''
        app = AppTest.from_string(script, default_timeout=20).run()
        for index in (0, 1):
            self.widget(app, "selectbox", "Point de départ").set_value(str(index)).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.warning)
