import copy
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from src.visualization import apply_filters, chart_data, infer_roles, prepare, suggestions, validate_configuration


class VisualizationTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.DataFrame({"id": [1, 2, 3, 4], "group": ["a", "a", "b", None],
                                 "hours": [1., 3., 8., None], "cost": [5., 8., 10., 2.],
                                 "opened_at": ["2026-01-01", "2026-01-31 23:59", "2026-03-01", "bad"]})
        self.roles = infer_roles(self.raw)
        self.data, self.invalid = prepare(self.raw, self.roles)

    def test_roles_conversion_and_source_preservation(self):
        original = self.raw.copy(deep=True)
        self.assertEqual(self.roles["id"], "Identifiant")
        self.assertEqual(self.roles["opened_at"], "Date")
        self.assertEqual(self.invalid, {"opened_at": 1})
        self.assertFalse(any(c["x"] == "id" or c["y"] == "id" for c in suggestions(self.roles)))
        assert_frame_equal(self.raw, original)

    def test_intersection_and_missing_filters(self):
        global_filter = [{"column": "group", "type": "Catégorie", "values": ["a"], "missing": False}]
        local_filter = [{"column": "hours", "type": "Mesure", "low": 2., "high": 10., "missing": False}]
        result = apply_filters(apply_filters(self.data, global_filter), local_filter)
        self.assertEqual(result.id.tolist(), ["2"])
        empty = apply_filters(self.data, [{**global_filter[0], "values": [], "missing": False}])
        self.assertTrue(empty.empty)
        missing = apply_filters(self.data, [{**global_filter[0], "values": [], "missing": True}])
        self.assertEqual(missing.id.tolist(), ["4"])

    def test_end_date_includes_entire_day(self):
        result = apply_filters(self.data, [{"column": "opened_at", "type": "Date", "low": "2026-01-01", "high": "2026-01-31", "missing": False}])
        self.assertEqual(len(result), 2)

    def test_aggregation_sort_and_excluded_rows(self):
        spec = next(s for s in suggestions(self.roles) if s["kind"] == "Barres" and s["y"] == "hours")
        frame, excluded = chart_data(self.data, spec)
        self.assertEqual(frame.Groupe.tolist(), ["b", "a"])
        self.assertEqual(frame.Valeur.tolist(), [8., 2.])
        self.assertEqual(excluded, 1)

    def test_empty_month_is_not_zero_sum(self):
        spec = next(s for s in suggestions(self.roles) if s["kind"] == "Courbe" and s["y"] == "hours")
        spec["agg"] = "Somme"
        frame, _ = chart_data(self.data, spec)
        self.assertTrue(pd.isna(frame.Valeur.iloc[1]))

    def test_round_trip_and_reject_invalid_configuration(self):
        config = {"version": 1, "roles": self.roles, "filters": [], "charts": suggestions(self.roles)}
        validate_configuration(config, self.roles)
        invalid = copy.deepcopy(config)
        invalid["charts"][0]["x"] = "absent"
        with self.assertRaises(ValueError):
            validate_configuration(invalid, self.roles)
        invalid = copy.deepcopy(config)
        invalid["filters"] = [{"column": "hours", "type": "Mesure", "low": 10, "high": 2, "missing": False}]
        with self.assertRaises(ValueError):
            validate_configuration(invalid, self.roles)

    def test_group_column_names_do_not_collide_with_result_columns(self):
        base = {"period": "Mois", "sort": "Groupe", "limit": 20, "filters": []}
        for name in ["Valeur", "Groupe", "Série"]:
            data = pd.DataFrame({name: ["a", "b", "a"], "m": [1., 2., 3.], "c": ["x", "y", "x"]})
            frame, _ = chart_data(data, dict(base, kind="Barres", x=name, y=None, agg="Effectif"))
            self.assertEqual(frame.to_dict("list"), {"Groupe": ["a", "b"], "Valeur": [2, 1]})
            frame, _ = chart_data(data, dict(base, kind="Barres", x=name, y="m", agg="Moyenne"))
            self.assertEqual(frame.Valeur.tolist(), [2., 2.])
            frame, _ = chart_data(data, dict(base, kind="Tableau croisé", x=name, y="c", agg="Effectif"))
            self.assertEqual(list(frame), ["Groupe", "Série", "Valeur"])
        dates = pd.DataFrame({"Valeur": pd.to_datetime(["2026-01-05", "2026-02-01"]), "Groupe": [1., 3.]})
        frame, _ = chart_data(dates, dict(base, kind="Courbe", x="Valeur", y="Groupe", agg="Moyenne"))
        self.assertEqual(frame.Valeur.tolist(), [1., 3.])

    def test_roles_from_french_names_and_iso_content(self):
        data = pd.DataFrame({"N° commande": [1, 2], "matricule": [10, 20], "Numéro client": [5, 6],
                             "réf_produit": ["a", "b"], "horodatage": ["x", "y"],
                             "instant": ["2026-03-10T08:00:00+01:00", "2026-03-11 09:30"],
                             "code postal texte": ["75001", "69002"], "libellé": ["2026", "texte"],
                             "montant": [1.5, 2.5], "valide": [True, False]})
        roles = infer_roles(data)
        for col in ["N° commande", "matricule", "Numéro client", "réf_produit", "code postal texte"]:
            self.assertEqual(roles[col], "Identifiant", col)
        self.assertEqual(roles["horodatage"], "Date")
        self.assertEqual(roles["instant"], "Date")
        self.assertEqual(roles["libellé"], "Catégorie")
        self.assertEqual(roles["montant"], "Mesure")
        self.assertEqual(roles["valide"], "Catégorie")
        self.assertEqual(infer_roles(pd.DataFrame({"note": ["2026-01-01", "pas une date"]}))["note"], "Catégorie")

    def test_exclusion_filter_and_missing_values(self):
        data = pd.DataFrame({"g": ["a", "b", None, "c"]})
        spec = {"column": "g", "type": "Catégorie", "values": ["a"], "missing": False, "exclude": True}
        self.assertEqual(apply_filters(data, [spec]).g.tolist(), ["b", "c"])
        self.assertEqual(apply_filters(data, [dict(spec, missing=True)]).index.tolist(), [1, 2, 3])
        self.assertEqual(apply_filters(data, [dict(spec, values=[], exclude=True)]).g.tolist(), ["a", "b", "c"])
        self.assertEqual(apply_filters(data, [{k: v for k, v in spec.items() if k != "exclude"}]).g.tolist(), ["a"])
        roles = {"g": "Catégorie"}
        validate_configuration({"version": 1, "roles": roles, "charts": [], "filters": [spec]}, roles)
        with self.assertRaises(ValueError):
            validate_configuration({"version": 1, "roles": roles, "charts": [], "filters": [dict(spec, exclude="oui")]}, roles)

    def test_updated_by_is_not_proposed_as_date(self):
        roles = infer_roles(pd.DataFrame({"sys_updated_by": ["x"], "sys_updated_at": ["2026-01-01"], "date_update": ["2026-01-01"]}))
        self.assertEqual(roles, {"sys_updated_by": "Catégorie", "sys_updated_at": "Date", "date_update": "Date"})

    def test_numeric_dates_are_years_never_nanoseconds(self):
        data = pd.DataFrame({"annee": [2023, 2024, None, 2025.5]})
        result, invalid = prepare(data, {"annee": "Date"})
        self.assertEqual(result.annee.iloc[0], pd.Timestamp("2023-01-01"))
        self.assertEqual(result.annee.iloc[1], pd.Timestamp("2024-01-01"))
        self.assertEqual(invalid, {"annee": 1})
        self.assertTrue((result.annee.dropna().dt.year > 1970).all())

    def test_ambiguous_dates_use_one_format_per_column(self):
        data = pd.DataFrame({"jour": ["03/04/2026", "13/04/2026"]})
        result, invalid = prepare(data, {"jour": "Date"}, dayfirst=False)
        self.assertEqual(result.jour.iloc[0], pd.Timestamp("2026-03-04"))
        self.assertEqual(invalid, {"jour": 1})
        result, invalid = prepare(data, {"jour": "Date"}, dayfirst=True)
        self.assertEqual(result.jour.tolist(), [pd.Timestamp("2026-04-03"), pd.Timestamp("2026-04-13")])
        self.assertEqual(invalid, {})
