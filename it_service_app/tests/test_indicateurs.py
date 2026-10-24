"""Tests des KPI : populations, indicateurs incalculables, filtres, et comparaison au notebook.

La comparaison au notebook utilise data/processed/incident_clean.csv (non versionné) : elle est sautée s'il manque.
"""
import io
import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indicateurs import (calculer_kpi, effet_reassignation, filtrer, format_fr, lecture, plus_longs,  # noqa: E402
                         sla_par_equipe, sla_par_mois, sla_par_priorite)
from preparation import lire_csv, preparer  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
INCIDENT_CLEAN = RACINE / "data" / "processed" / "incident_clean.csv"
JOURNAL_BRUT = RACINE / "data" / "raw" / "incident_event_log.csv"

EXEMPLE = b"""number,incident_state,reassignment_count,made_sla,opened_at,sys_updated_at,resolved_at,closed_at,priority,category,assignment_group
INC1,Closed,2,true,1/3/2016 08:00,5/3/2016 10:00,1/3/2016 10:00,5/3/2016 10:00,3 - Moderate,A,G1
INC2,Closed,0,false,1/4/2016 08:00,5/4/2016 10:00,1/4/2016 12:00,5/4/2016 10:00,1 - Critical,B,G1
INC3,New,0,true,2/4/2016 08:00,2/4/2016 08:00,?,?,3 - Moderate,A,G2
"""


def kpi(kpis, nom):
    return next(k for k in kpis if k["indicateur"] == nom)


class Indicateurs(unittest.TestCase):
    def setUp(self):
        self.incidents, _, _ = preparer(lire_csv(EXEMPLE))

    def test_kpi_et_populations(self):
        kpis = calculer_kpi(self.incidents)
        self.assertEqual(kpi(kpis, "Incidents uniques")["valeur"], 3)
        self.assertEqual(kpi(kpis, "Incidents résolus")["valeur"], 2)
        self.assertEqual(kpi(kpis, "Incidents ouverts")["valeur"], 1)
        self.assertEqual(kpi(kpis, "Délai moyen de résolution")["valeur"], 3.0)  # (2 h + 4 h) / 2
        self.assertEqual(kpi(kpis, "Délai médian de résolution")["valeur"], 3.0)
        self.assertEqual(kpi(kpis, "Respect des SLA")["valeur"], 66.67)  # 2 / 3, ouverts compris
        self.assertEqual(kpi(kpis, "Respect des SLA (résolus)")["valeur"], 50.0)
        self.assertEqual(kpi(kpis, "Taux d'incidents réassignés")["valeur"], 33.33)
        self.assertTrue(kpi(kpis, "Délai moyen de résolution")["population"].startswith("2 incidents"))

    def test_sla_et_reassignations_incalculables(self):
        sans = self.incidents.drop(columns=["made_sla", "reassignment_count"]).assign(
            sla_compliant=pd.NA, has_reassignment=pd.NA)
        kpis = calculer_kpi(sans)
        self.assertIsNone(kpi(kpis, "Respect des SLA")["valeur"])
        self.assertIn("made_sla", kpi(kpis, "Respect des SLA")["indisponible"])
        self.assertIn("événement", kpi(kpis, "Réassignations moyennes")["indisponible"])

    def test_filtres(self):
        avril = filtrer(self.incidents, date(2016, 4, 1), date(2016, 4, 30))
        self.assertEqual(sorted(avril["number"]), ["INC2", "INC3"])
        g1_moderate = filtrer(self.incidents, choix={"assignment_group": ["G1"], "priority": ["3 - Moderate"]})
        self.assertEqual(list(g1_moderate["number"]), ["INC1"])

    def test_filtre_sans_resultat(self):
        vide = filtrer(self.incidents, choix={"category": ["Z"]})
        self.assertEqual(calculer_kpi(vide), [kpi(calculer_kpi(vide), "Incidents uniques")])
        self.assertTrue(sla_par_equipe(vide).empty)
        self.assertTrue(effet_reassignation(vide).empty)
        self.assertTrue(plus_longs(vide).empty)

    def test_sla_par_priorite_et_par_mois(self):
        priorites = sla_par_priorite(self.incidents).set_index("priority")
        self.assertEqual(priorites.loc["3 - Moderate", "incidents"], 2)
        self.assertEqual(priorites.loc["3 - Moderate", "sla_pct"], 100.0)
        self.assertEqual(priorites.loc["1 - Critical", "sla_pct"], 0.0)
        mois = sla_par_mois(self.incidents).set_index("mois")
        self.assertEqual(mois.loc["2016-04", "incidents"], 2)
        self.assertEqual(mois.loc["2016-04", "sla_pct"], 50.0)

    def test_effet_reassignation(self):
        effet = effet_reassignation(self.incidents).set_index("reassignment_status")
        self.assertEqual(effet.loc["Avec réassignation", "incidents"], 1)
        self.assertEqual(effet.loc["Avec réassignation", "resolution_moyenne_h"], 2.0)
        self.assertEqual(effet.loc["Sans réassignation", "incidents"], 2)
        self.assertEqual(effet.loc["Sans réassignation", "sla_pct"], 50.0)
        self.assertEqual(effet.loc["Sans réassignation", "resolution_moyenne_h"], 4.0)  # INC3 sans délai, exclu

    def test_plus_longs(self):
        self.assertEqual(list(plus_longs(self.incidents)["number"]), ["INC2", "INC1"])

    def test_lecture(self):
        messages = lecture(self.incidents, calculer_kpi(self.incidents))
        self.assertIn("66,67 %", messages[0])
        self.assertTrue(any("`1 - Critical` (0,00 %" in m for m in messages))  # 66,67 − 0 ≥ 10 points
        self.assertTrue(any("réassignés sont résolus en **2,00 h**" in m for m in messages))

    def test_lecture_sans_sla_ni_reassignation(self):
        sans = self.incidents.assign(sla_compliant=pd.NA, reassignment_count=pd.NA, has_reassignment=pd.NA)
        messages = lecture(sans, calculer_kpi(sans))
        self.assertFalse(any("SLA" in m or "réassign" in m for m in messages))

    def test_format_fr(self):
        self.assertEqual(format_fr(24918), "24 918")
        self.assertEqual(format_fr(63.45, "%"), "63,45 %")
        self.assertEqual(format_fr(None, "heures"), "—")


@unittest.skipUnless(INCIDENT_CLEAN.exists(), "data/processed/incident_clean.csv absent")
class ComparaisonNotebook(unittest.TestCase):
    """Sur incident_clean.csv, l'application retrouve les KPI du notebook 03/05."""

    @classmethod
    def setUpClass(cls):
        cls.incidents, _, _ = preparer(lire_csv(INCIDENT_CLEAN.read_bytes()))

    def test_memes_tableaux_que_le_notebook(self):
        # Valeurs des notebooks 03 à 05 après la correction des ex-aequo (24/10/2026).
        priorites = sla_par_priorite(self.incidents).set_index("priority")
        self.assertEqual(priorites.loc["1 - Critical", "sla_pct"], 1.85)
        self.assertEqual(priorites.loc["2 - High", "sla_pct"], 0.49)
        self.assertEqual(priorites.loc["3 - Moderate", "resolution_moyenne_h"], 174.35)
        effet = effet_reassignation(self.incidents).set_index("reassignment_status")
        self.assertEqual(effet.loc["Avec réassignation", "incidents"], 11369)
        self.assertEqual(effet.loc["Avec réassignation", "sla_pct"], 45.58)
        self.assertEqual(effet.loc["Sans réassignation", "resolution_moyenne_h"], 94.98)
        equipes = sla_par_equipe(self.incidents, top=10).set_index("assignment_group")
        self.assertEqual(equipes.loc["Group 70", "sla_pct"], 83.84)
        self.assertEqual(equipes.loc["Group 64", "resolution_moyenne_h"], 18.75)
        self.assertEqual(sla_par_mois(self.incidents).set_index("mois").loc["2016-03", "sla_pct"], 39.86)
        self.assertEqual(plus_longs(self.incidents)["number"].iloc[0], "INC0001839")

    @unittest.skipUnless(JOURNAL_BRUT.exists(), "data/raw/incident_event_log.csv absent")
    def test_journal_brut_donne_la_table_du_notebook(self):
        """Préparer le journal brut dans l'application redonne incident_clean.csv, cellule par cellule."""
        lire = dict(dtype=str, keep_default_na=False)
        reference = pd.read_csv(INCIDENT_CLEAN, **lire).set_index("number").sort_index()
        incidents, _, _ = preparer(lire_csv(JOURNAL_BRUT.read_bytes()))
        application = pd.read_csv(io.StringIO(incidents.to_csv(index=False)), **lire).set_index("number").sort_index()
        pd.testing.assert_frame_equal(application, reference)

    def test_memes_kpi_que_le_notebook(self):
        incidents = self.incidents
        kpis = calculer_kpi(incidents)
        self.assertEqual(kpi(kpis, "Incidents uniques")["valeur"], 24918)
        self.assertEqual(kpi(kpis, "Respect des SLA")["valeur"], 63.42)
        self.assertEqual(kpi(kpis, "Incidents ouverts")["valeur"], 0)
        self.assertEqual(kpi(kpis, "Délai moyen de résolution")["valeur"], 178.17)
        self.assertEqual(kpi(kpis, "Réassignations moyennes")["valeur"], 0.94)
        self.assertEqual(kpi(kpis, "Réouvertures moyennes")["valeur"], 0.01)


if __name__ == "__main__":
    unittest.main()
