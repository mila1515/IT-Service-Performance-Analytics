"""Tests des règles de préparation : incidents uniques, dernier état, dates, durées, SLA.

Lancer depuis la racine : python -m unittest discover -s it_service_app/tests
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preparation import COLONNES_CALCULEES, FichierIncompatible, lire_csv, preparer  # noqa: E402

ENTETE = "number,incident_state,reassignment_count,reopen_count,sys_mod_count,made_sla,opened_at,sys_updated_at,resolved_at,closed_at,priority,category,assignment_group"


def csv(*lignes):
    return ("\n".join([ENTETE, *lignes]) + "\n").encode("utf-8")


class Preparation(unittest.TestCase):
    def test_journal_reduit_au_dernier_etat(self):
        data = lire_csv(csv(
            "INC1,New,0,0,0,true,1/3/2016 08:00,1/3/2016 08:00,?,?,3 - Moderate,Cat A,G1",
            "INC1,Closed,1,0,2,false,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,Cat A,G1",
            "INC2,Resolved,0,0,1,true,2/3/2016 09:30,2/3/2016 12:00,2/3/2016 11:30,?,1 - Critical,?,?"))
        incidents, controles, infos = preparer(data)
        self.assertEqual(infos["format"], "journal d'événements")
        self.assertEqual(len(incidents), 2)
        inc1 = incidents.set_index("number").loc["INC1"]
        self.assertEqual(inc1["incident_state"], "Closed")
        self.assertEqual(inc1["reassignment_count"], 1)
        self.assertEqual(inc1["resolution_time_hours"], 24.0)
        self.assertEqual(inc1["closure_time_hours"], 98.0)
        self.assertEqual(inc1["sla_compliant"], 0)
        inc2 = incidents.set_index("number").loc["INC2"]
        self.assertEqual(inc2["resolution_time_hours"], 2.0)
        self.assertEqual(inc2["assignment_group"], "Inconnu")
        self.assertEqual(inc2["priority_level"], 1)
        self.assertEqual(list(incidents.columns[-len(COLONNES_CALCULEES):]), COLONNES_CALCULEES)
        self.assertEqual(infos["lignes_par_incident"], 1.5)
        self.assertEqual([d.strftime("%d/%m/%Y") for d in infos["periode"]], ["01/03/2016", "02/03/2016"])
        manquants = infos["manquants"].set_index("colonne")
        self.assertEqual(manquants.loc["resolved_at", "valeurs_manquantes"], 1)  # « ? » compté comme manquant
        self.assertEqual(manquants.loc["closed_at", "taux_manquant_pct"], 66.67)
        self.assertNotIn("number", manquants.index)  # seules les colonnes incomplètes sont listées

    def test_ex_aequo_departages_par_sys_mod_count(self):
        data = lire_csv(csv(
            "INC1,Closed,0,0,5,true,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1",
            "INC1,Resolved,0,0,4,true,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1"))
        incidents, controles, _ = preparer(data)
        self.assertEqual(incidents.loc[0, "incident_state"], "Closed")
        ligne = controles.set_index("contrôle").loc["Incidents dont le dernier état est ex-aequo"]
        self.assertEqual(ligne["valeur"], 1)

    def test_vrais_doublons_distingues_des_evenements(self):
        ligne = "INC1,Closed,0,0,1,true,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1"
        _, controles, _ = preparer(lire_csv(csv(ligne, ligne)))
        valeurs = controles.set_index("contrôle")["valeur"]
        self.assertEqual(valeurs["Lignes strictement identiques (vrais doublons)"], 1)
        self.assertEqual(valeurs["Incidents présents sur plusieurs lignes (événements)"], 1)

    def test_dates_invalides_et_durees_negatives_comptees(self):
        data = lire_csv(csv(
            "INC1,Closed,0,0,1,true,pas une date,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1",
            "INC2,Closed,0,0,1,true,3/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1",
            "INC3,Closed,0,0,1,true,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1"))
        incidents, controles, _ = preparer(data)
        valeurs = controles.set_index("contrôle")["valeur"]
        self.assertEqual(valeurs["Dates invalides : opened_at"], 1)
        self.assertEqual(valeurs["Délais de résolution négatifs"], 1)
        self.assertEqual(len(incidents), 3)  # aucune ligne supprimée
        self.assertEqual(incidents["resolution_time_hours"].notna().sum(), 1)

    def test_sla_illisible_reste_manquant(self):
        data = lire_csv(csv(
            "INC1,Closed,0,0,1,peut-être,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1"))
        incidents, controles, _ = preparer(data)
        self.assertTrue(pd.isna(incidents.loc[0, "sla_compliant"]))
        self.assertEqual(controles.set_index("contrôle").loc["Statut SLA vide ou illisible (made_sla)", "valeur"], 1)

    def test_cloture_ignoree_si_incident_non_clos(self):
        data = lire_csv(csv(
            "INC1,Resolved,0,0,1,true,1/3/2016 08:00,5/3/2016 10:00,2/3/2016 08:00,5/3/2016 10:00,3 - Moderate,A,G1"))
        incidents, _, _ = preparer(data)
        self.assertTrue(pd.isna(incidents.loc[0, "closure_time_hours"]))

    def test_format_iso_de_incident_clean(self):
        contenu = (ENTETE + "\nINC1,Closed,0,0,1,True,2016-03-01 08:00:00,2016-03-05 10:00:00,"
                   "2016-03-02 08:00:00,2016-03-05 10:00:00,3 - Moderate,A,G1\n").encode()
        incidents, _, infos = preparer(lire_csv(contenu))
        self.assertEqual(infos["format"], "table d'incidents")
        self.assertEqual(infos["formats_dates"]["opened_at"], "%Y-%m-%d %H:%M:%S")
        self.assertEqual(incidents.loc[0, "resolution_time_hours"], 24.0)

    def test_fichier_incompatible(self):
        with self.assertRaises(FichierIncompatible):
            preparer(lire_csv(b"nom,age\nAda,36\n"))

    def test_journal_sans_date_de_mise_a_jour(self):
        contenu = b"number,opened_at\nINC1,1/3/2016 08:00\nINC1,1/3/2016 08:00\n"
        with self.assertRaises(FichierIncompatible):
            preparer(lire_csv(contenu))

    def test_point_virgule_accepte(self):
        data = lire_csv(b"number;opened_at\nINC1;1/3/2016 08:00\n")
        self.assertEqual(list(data.columns), ["number", "opened_at"])


if __name__ == "__main__":
    unittest.main()
