"""Assistant IA : rien de sensible dans le résumé, réponses contrôlées, rapport et cartes, sans appel réel à l'API."""
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.etape2_comprendre.colonnes import dictionnaire_propose, resume_colonnes
from src.etape2_comprendre.diagnostic import diagnose
from src.etape2_comprendre.points import detecter_points
from src.etape4_visualiser.rapport import rapport_html, rapport_markdown
from src.etape4_visualiser.rapport_word import rapport_word
from src.ia import client
from src.ia.conseils import lire_comprendre, lire_pistes, lire_suggestions, pour_le_rapport, retablir_noms
from src.ia.ecran import sans_mise_en_forme
from src.ia.resume import construire_resume
from src.tests.etape4_visualiser.test_rapport import contenu

APP = str(Path(__file__).parents[2] / "app.py")
EXEMPLE = Path(__file__).parents[1] / "fixtures" / "exemple.csv"
SECRET = "Valeur-Secrete-Dupont"


def preparer(masquer=False):
    """Un fichier avec une valeur reconnaissable, un code manquant, du texte dans des nombres, des doublons."""
    raw = pd.DataFrame({"client": [SECRET, "Martin", "Martin", None, "Durand", "Durand", "?"] * 3,
                        "montant": ["10", "20", "20", "30", "SECRET-TEXTE", "40", "50"] * 3,
                        "jour": ["05/03/2024", "06/03/2024", "06/03/2024", "07/03/2024", "08/03/2024", "09/03/2024",
                                 "10/03/2024"] * 3})
    dictionnaire = dictionnaire_propose(raw)
    diagnostic = diagnose(raw, dictionnaire, ignore_markers=True)
    points = detecter_points(raw, dictionnaire, {}, diagnostic)
    fiches = resume_colonnes(raw, dictionnaire)
    return points, *construire_resume(raw, dictionnaire, points, diagnostic, fiches, masquer)


class Resume(unittest.TestCase):
    def test_aucune_valeur_du_fichier_n_est_envoyee(self):
        _, resume, _, _ = preparer()
        envoye = json.dumps(resume, ensure_ascii=False)
        for valeur in (SECRET, "SECRET-TEXTE", "Martin", "Durand", "05/03/2024 ("):
            self.assertNotIn(valeur, envoye)
        self.assertIn("client", envoye)
        self.assertTrue(resume["points"])

    def test_noms_masques(self):
        _, resume, _, noms = preparer(masquer=True)
        envoye = json.dumps(resume, ensure_ascii=False)
        for nom in ("client", "montant", "jour"):
            self.assertNotIn(nom, envoye)
        self.assertIn("Colonne 1", envoye)
        self.assertEqual(retablir_noms("Voir Colonne 2 et Colonne 9.", noms), "Voir montant et Colonne 9.")

    def test_chaque_point_a_ses_choix(self):
        points, resume, references, _ = preparer()
        self.assertEqual(len(resume["points"]), sum(len(p["lignes"]) for p in points))
        self.assertEqual(set(references), {p["id"] for p in resume["points"]})
        self.assertTrue(all(p["choix_possibles"] for p in resume["points"]))


class Reponses(unittest.TestCase):
    def test_seuls_les_choix_de_la_carte_sont_gardes(self):
        points, resume, references, noms = preparer()
        premier = resume["points"][0]
        bon = premier["choix_possibles"][0]["cle"]
        reponse = {"suggestions": [{"point": premier["id"], "choix": bon, "raison": "Peu de cas."},
                                   {"point": premier["id"], "choix": bon, "raison": "En double."},
                                   {"point": "P999", "choix": bon, "raison": "Inconnu."},
                                   {"point": "P2", "choix": "tout_supprimer", "raison": "Inventé."},
                                   "pas un dictionnaire"]}
        gardees = lire_suggestions(reponse, references, points, noms)
        self.assertEqual([s["raison"] for s in gardees], ["Peu de cas."])
        self.assertEqual(gardees[0]["cle"], references[premier["id"]]["cle"])

    def test_reponses_mal_formees(self):
        points, _, references, noms = preparer()
        for reponse in ({}, [], "texte", {"suggestions": "non", "pistes": 3, "a_regarder": "non"}):
            self.assertEqual(lire_suggestions(reponse, references, points, noms), [])
            self.assertEqual(lire_pistes(reponse, noms), [])
            self.assertEqual(lire_comprendre(reponse, noms)["a_regarder"], [])

    def test_seules_les_analyses_de_l_etape_5(self):
        pistes = lire_pistes({"pistes": [{"question": "Q1", "analyse": "Comparer des groupes", "colonnes": ["a"]},
                                         {"question": "Q2", "analyse": "Réseau de neurones"}]}, {})
        self.assertEqual([p["question"] for p in pistes], ["Q1"])

    def test_le_texte_recu_n_ajoute_ni_lien_ni_image(self):
        texte = sans_mise_en_forme("![x](http://exemple.test) <b>gras</b> :material/key:")
        self.assertNotIn("](", texte)
        self.assertIn("\\:material", texte)  # le code d'icône est neutralisé
        self.assertIn("\\<b\\>", texte)


class Cle(unittest.TestCase):
    def test_lue_dans_l_environnement_puis_dans_le_fichier(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": " abc "}):
            self.assertEqual(client.cle_api(), "abc")
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch.object(client, "FICHIER_ENV", Path("absent.env")):
            self.assertEqual(client.cle_api(), "")


SUGGESTION = {"type": "t", "cle": "c", "probleme": "Cases vides", "choix": "a", "raison": "Peu de cas.",
              "options": {"a": "Laisser vide", "b": "Écarter"}}


class Rapport(unittest.TestCase):
    def test_sans_ia_le_rapport_ne_change_pas(self):
        self.assertIsNone(pour_le_rapport(None, {}))
        self.assertIsNone(pour_le_rapport({"corriger": [], "analyser": []}, {}))
        self.assertEqual(rapport_markdown(contenu(ia=None)), rapport_markdown(contenu()))
        self.assertNotIn("Suggestions de l'IA", rapport_markdown(contenu()))

    def test_decision_suivie_ou_non(self):
        suivie = pour_le_rapport({"corriger": [SUGGESTION]}, {"t": {"c": "a"}})["suggestions"][0]
        autre = pour_le_rapport({"corriger": [SUGGESTION]}, {"t": {"c": "b"}})["suggestions"][0]
        absente = pour_le_rapport({"corriger": [SUGGESTION]}, {})["suggestions"][0]
        self.assertEqual(suivie[3:], ["Laisser vide", "suivie"])
        self.assertEqual(autre[3:], ["Écarter", "non suivie"])
        self.assertEqual(absente[3:], ["—", "—"])

    def test_section_dans_les_trois_formats(self):
        ia = pour_le_rapport({"comprendre": {"resume": "Un fichier de ventes.", "a_regarder": ["Les vides"]},
                              "corriger": [SUGGESTION],
                              "analyser": [{"question": "Q1 ?", "analyse": "Mesurer un délai", "colonnes": ["a"], "pourquoi": ""}]},
                             {"t": {"c": "a"}})
        document = contenu(ia=ia)
        for texte in (rapport_markdown(document), rapport_html(document)):
            for attendu in ("Un fichier de ventes.", "Peu de cas.", "suivie", "Q1 ?"):
                self.assertIn(attendu, texte)
        self.assertTrue(rapport_word(document).startswith(b"PK"))
        self.assertLess(rapport_markdown(document).index("Suggestions de l'IA"),
                        rapport_markdown(document).index("Ce que ce rapport ne garantit pas"))


def ouvrir(cle="cle-de-test"):
    app = AppTest.from_file(APP, default_timeout=60)
    with patch.dict(os.environ, {"OPENAI_API_KEY": cle}), patch.object(client, "FICHIER_ENV", Path("absent.env")):
        app.run()
        app.button(key="w_exemple").click().run()
    return app


class Onglet(unittest.TestCase):
    def aller(self, app, etape, cle="cle-de-test"):
        with patch.dict(os.environ, {"OPENAI_API_KEY": cle}), patch.object(client, "FICHIER_ENV", Path("absent.env")):
            app.session_state.etape = etape
            app.run()
        self.assertFalse(app.exception)
        return app

    def test_sans_cle_tout_fonctionne(self):
        app = self.aller(ouvrir(""), "Assistant IA", "")
        self.assertIn("Clé API à configurer", " ".join(str(i.proto) for i in app.info))
        self.assertFalse(app.button)
        self.aller(app, "Corriger", "")
        self.assertFalse(any("Suggestion IA" in c.value for c in app.caption))

    def test_rien_n_est_envoye_sans_clic(self):
        with patch.object(client, "demander") as demander:
            app = self.aller(ouvrir(), "Assistant IA")
        demander.assert_not_called()
        self.assertTrue(app.checkbox(key="w_ia_masquer"))

    def test_conseil_affiche_sous_la_carte_sans_cocher_le_choix(self):
        app = self.aller(ouvrir(), "Assistant IA")
        reponse = {"suggestions": [{"point": f"P{i}", "choix": "ecarter", "raison": "Raison de test."} for i in range(1, 30)]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "cle-de-test"}), patch.object(client, "demander", return_value=reponse) as demander:
            app.segmented_control(key="w_ia_vue").set_value("corriger").run()
            demander.assert_not_called()  # changer de partie n'appelle pas l'IA
            app.button(key="w_ia_demander").click().run()
            self.assertIn("Raison de test.", " ".join(m.value for m in app.markdown))
            self.assertEqual(app.button(key="w_ia_demander").label, "Redemander à l'IA")
            app.segmented_control(key="w_ia_vue").set_value("analyser").run()
            self.assertNotIn("Raison de test.", " ".join(m.value for m in app.markdown))  # une seule partie à la fois
            app.segmented_control(key="w_ia_vue").set_value("corriger").run()
            self.assertIn("Raison de test.", " ".join(m.value for m in app.markdown))  # réponse conservée
        self.assertFalse(app.exception)
        demander.assert_called_once()
        self.assertTrue(app.session_state.ia["corriger"])
        self.assertFalse(app.session_state.choix)  # aucun choix coché par l'IA
        self.aller(app, "Corriger")
        self.assertTrue(any("Suggestion IA" in c.value and "Raison de test" in c.value for c in app.caption))
        self.assertFalse(app.session_state.choix)

    def test_erreur_de_l_api_affichee_sans_bloquer(self):
        app = self.aller(ouvrir(), "Assistant IA")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "cle-de-test"}), patch.object(client, "demander", side_effect=client.ErreurIA("Quota dépassé")):
            app.button(key="w_ia_demander").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.error[0].value, "Quota dépassé")
        self.aller(app, "Comprendre")


class Appel(unittest.TestCase):
    def test_reponse_json_lue(self):
        contenu_recu = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"resume": "ok"}'))])
        faux = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: contenu_recu)))
        with patch("openai.OpenAI", return_value=faux), patch.dict(os.environ, {"OPENAI_API_KEY": "x"}):
            self.assertEqual(client.demander([]), {"resume": "ok"})

    def test_reponse_illisible(self):
        contenu_recu = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="pas du json"))])
        faux = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: contenu_recu)))
        with patch("openai.OpenAI", return_value=faux), patch.dict(os.environ, {"OPENAI_API_KEY": "x"}):
            with self.assertRaises(client.ErreurIA):
                client.demander([])


if __name__ == "__main__":
    unittest.main()
