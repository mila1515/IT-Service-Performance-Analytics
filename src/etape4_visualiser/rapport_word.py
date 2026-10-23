"""Étape 4 (Exporter) : le rapport qualité en document Word (.docx), avec les graphiques en images.

Entrée : le même `contenu` que `rapport.py` (voir sa description). Sortie : les octets du fichier .docx.
Mêmes sections que le rapport HTML ; les graphiques sont les images PNG des graphiques de l'écran.
Les caractères de contrôle, refusés par le format Word, sont retirés du texte issu du fichier.
"""
import io
import re

import vl_convert
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from src.core.texte import nombre_lisible
from src.etape2_comprendre.repetitions import part_lisible
from src.etape4_visualiser.rapport import (LIMITES, LOGO, NOTE_PISTES, NOTE_REGLES, RIEN_A_SIGNALER, lignes_regles,
                                           lignes_resultat, png_graphique, resume_fiche, synthese)

SARCELLE = RGBColor(0x0B, 0x6F, 0x71)
ENCRE = RGBColor(0x1E, 0x2A, 0x38)
GRIS = RGBColor(0x5B, 0x66, 0x73)
FOND_ENTETE = "E3F2F2"
LARGEUR_IMAGE = Cm(16)
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _propre(texte):
    return _CONTROLE.sub("", str(texte))


class _Document:
    """Petites briques de mise en page, aux couleurs de l'outil."""

    def __init__(self):
        self.doc = Document()
        for section in self.doc.sections:
            section.left_margin = section.right_margin = Cm(2)
            section.top_margin = section.bottom_margin = Cm(1.8)
        normal = self.doc.styles["Normal"]
        normal.font.name, normal.font.size, normal.font.color.rgb = "Calibri", Pt(10.5), ENCRE
        for nom, taille in (("Title", 22), ("Heading 1", 15), ("Heading 2", 12)):
            style = self.doc.styles[nom]
            style.font.color.rgb, style.font.size, style.font.name = SARCELLE if nom != "Title" else ENCRE, Pt(taille), "Calibri"

    def titre(self, texte):
        self.doc.add_heading(_propre(texte), level=0)

    def section(self, texte):
        self.doc.add_heading(_propre(texte), level=1)

    def sous_titre(self, texte):
        self.doc.add_heading(_propre(texte), level=2)

    def paragraphe(self, texte="", gras=None, discret=False):
        paragraphe = self.doc.add_paragraph()
        if gras:
            paragraphe.add_run(_propre(gras)).bold = True
        run = paragraphe.add_run(_propre(texte))
        if discret:
            run.font.color.rgb, run.font.size = GRIS, Pt(9.5)
        return paragraphe

    def puces(self, elements):
        for element in elements:
            self.doc.add_paragraph(_propre(element), style="List Bullet")

    def tableau(self, entetes, lignes):
        table = self.doc.add_table(rows=1, cols=len(entetes), style="Table Grid")
        for cellule, entete in zip(table.rows[0].cells, entetes):
            cellule.text = _propre(entete)
            cellule.paragraphs[0].runs[0].bold = True
            ombre = OxmlElement("w:shd")
            ombre.set(qn("w:val"), "clear")
            ombre.set(qn("w:fill"), FOND_ENTETE)
            cellule._tc.get_or_add_tcPr().append(ombre)
        for ligne in lignes:
            for cellule, valeur in zip(table.add_row().cells, ligne):
                cellule.text = _propre(valeur)
        for ligne in table.rows:
            for cellule in ligne.cells:
                for paragraphe in cellule.paragraphs:
                    for run in paragraphe.runs:
                        run.font.size = Pt(9)
        self.doc.add_paragraph()

    def image(self, png, largeur=LARGEUR_IMAGE):
        self.doc.add_picture(io.BytesIO(png), width=largeur)

    def octets(self):
        tampon = io.BytesIO()
        self.doc.save(tampon)
        return tampon.getvalue()


def _graphique(d, graphique):
    d.sous_titre(graphique["titre"])
    d.paragraphe(graphique["sous_titre"], discret=True)
    if graphique.get("donnees") is not None and len(graphique["donnees"]):
        d.image(png_graphique(graphique))


def rapport_word(contenu):
    """Document Word : mêmes sections que le rapport HTML, graphiques compris."""
    d = _Document()
    d.image(vl_convert.svg_to_png(LOGO.read_text(encoding="utf-8"), scale=3), largeur=Cm(6))
    d.titre(f"Rapport qualité — {contenu['nom']}")
    d.paragraphe(f"Produit le {contenu['produit_le']:%d/%m/%Y à %H:%M} (UTC).", discret=True)

    d.section("En bref")
    d.puces(synthese(contenu))
    d.section("Le fichier")
    d.puces([f"{nombre_lisible(contenu['lignes'])} lignes, {nombre_lisible(contenu['colonnes'])} colonnes.",
             f"Empreinte SHA-256 du fichier d'origine : {contenu['empreinte']}. Ce fichier n'a pas été modifié."])
    d.section("Les colonnes (après corrections)")
    d.tableau(["Colonne", "Type", "Remplie", "Valeurs différentes", "En résumé"],
              [[f["colonne"], f["libelle"], part_lisible(f["remplies"] / f["total"]) if f["total"] else "—",
                nombre_lisible(f["distinctes"]), resume_fiche(f)] for f in contenu["fiches"]])

    d.section("Points vérifiés et décisions")
    if contenu["decisions"]:
        for decision in contenu["decisions"]:
            paragraphe = d.doc.add_paragraph(style="List Bullet")
            paragraphe.add_run(_propre(f"{decision['texte']} → "))
            paragraphe.add_run(_propre(decision["choix"])).bold = True
    else:
        d.puces(["Aucun point à vérifier n'a été repéré."])
    d.section("Ce qui a été fait")
    d.puces(contenu["journal"])
    d.section("Résultat")
    d.puces(lignes_resultat(contenu["resultat"]))
    if contenu["resultat"]["ecartees"]:
        d.paragraphe("Les lignes écartées ne sont pas effacées : elles sont dans le fichier des lignes écartées, avec leur "
                     "raison. Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé.", discret=True)
    if contenu["regles_verifiees"]:
        d.section("Règles vérifiées")
        d.puces(lignes_regles(contenu["regles_verifiees"]))
        d.paragraphe(NOTE_REGLES, discret=True)
    if contenu["interpretations"]:
        d.section("Pistes de lecture")
        d.paragraphe(NOTE_PISTES, discret=True)
        d.puces(contenu["interpretations"])

    d.section("Graphiques de contrôle")
    filtre = contenu["filtre"]
    d.paragraphe(f"Filtre appliqué aux graphiques : {filtre['texte']} ({nombre_lisible(filtre['retenues'])} / "
                 f"{nombre_lisible(filtre['total'])} lignes). Les données téléchargées ne sont pas filtrées."
                 if filtre else "Calculés sur toutes les lignes gardées.", discret=True)
    for graphique in contenu["graphiques"]:
        _graphique(d, graphique)
        d.paragraphe(" ".join(graphique["a_retenir"]), gras="À retenir : ")

    if contenu["analyses"]:
        d.section("Analyses")
        d.paragraphe("Calculées sur les données corrigées, avec les colonnes choisies à l'étape Analyser.", discret=True)
        for analyse in contenu["analyses"]:
            _graphique(d, analyse)
            if analyse["tableau"] is not None and len(analyse["tableau"]):
                d.tableau(list(analyse["tableau"].columns), analyse["tableau"].itertuples(index=False))
            d.paragraphe(gras="Ce que montrent les chiffres")
            d.puces(analyse["a_retenir"] or [RIEN_A_SIGNALER])
            d.paragraphe(analyse["prudence"], discret=True)

    if contenu["notes"].strip():
        d.section("Notes")
        d.paragraphe(contenu["notes"].strip())
    d.section("Ce que ce rapport ne garantit pas")
    d.paragraphe(LIMITES)
    return d.octets()
