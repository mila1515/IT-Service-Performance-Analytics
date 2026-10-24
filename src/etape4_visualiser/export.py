"""Étape 4 (Exporter) : fichiers remis à la fin de l'audit qualité, avant l'analyse métier.

Entrées : fichier d'origine (octets), données corrigées, lignes écartées, choix et journal.
Sorties : CSV lisibles et archive ZIP du projet (le rapport lui-même est dans `rapport.py`).
Le fichier d'origine est recopié tel quel.
"""
import io
import json
import zipfile

import pandas as pd

from src.etape3_corriger.correction import motif_lisible


def csv_bytes(frame):
    """CSV en UTF-8 avec BOM, lisible directement par Excel."""
    return frame.to_csv(index=False).encode("utf-8-sig")


def rejets_lisibles(rejects):
    """Lignes écartées avec une seule ligne d'en-tête : « Ligne d'origine », « Raison », puis les colonnes du fichier."""
    resultat = pd.DataFrame({
        "Ligne d'origine": rejects[("Traçabilité", "Enregistrement source")].to_numpy(),
        "Raison": [" ; ".join(motif_lisible(m) for m in motifs.split(" ; "))
                   for motifs in rejects[("Traçabilité", "Motifs")]],
    })
    for niveau, colonne in rejects.columns:
        if niveau == "Donnée source":
            # Une colonne du fichier peut porter le même nom qu'une colonne de traçabilité.
            nom = f"{colonne} (donnée)" if colonne in resultat.columns else colonne
            resultat[nom] = rejects[(niveau, colonne)].to_numpy()
    return resultat


def archive_projet(source, nom_fichier, cleaned, rejects, rapport, choix, journal_moteur, dictionnaire, rapport_html=None,
                   autres=None):
    """Archive ZIP : fichier d'origine inchangé, données corrigées, lignes écartées, rapports et journal détaillé.

    `autres` : fichiers supplémentaires, chemin dans l'archive → octets (rapport Word, dossier données + notebook).
    """
    autres = autres or {}
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"fichier_origine/{nom_fichier}", source)
        archive.writestr("donnees_corrigees.csv", csv_bytes(cleaned))
        archive.writestr("lignes_ecartees.csv", csv_bytes(rejets_lisibles(rejects)))
        archive.writestr("rapport_qualite.md", rapport)
        if rapport_html is not None:
            archive.writestr("rapport_qualite.html", rapport_html)
        archive.writestr("journal.json", json.dumps({"choix": choix, "journal": journal_moteur, "dictionnaire": dictionnaire},
                                                    ensure_ascii=False, indent=2, default=str))
        for chemin, contenu in autres.items():
            archive.writestr(chemin, contenu)
        lignes = ["Audit qualité d'un fichier CSV avant analyse métier. Extrayez ce ZIP avant d'ouvrir les fichiers.", "",
                  "fichier_origine/ : le fichier importé, inchangé.",
                  "donnees_corrigees.csv : les données après vos corrections, dans le format de votre fichier.",
                  "lignes_ecartees.csv : lignes mises de côté, avec leur numéro d'origine et leur raison.",
                  "rapport_qualite.html : le rapport complet des étapes 1 à 5, avec les graphiques (navigateur).",
                  "rapport_qualite.md : le même rapport en texte."]
        if "rapport_qualite.docx" in autres:
            lignes.append("rapport_qualite.docx : le même rapport pour Word, graphiques compris.")
        lignes.append("journal.json : le détail des choix, du journal et des types de colonnes.")
        if any(c.startswith("donnees_et_notebook/") for c in autres):
            lignes.append("donnees_et_notebook/ : données typées (dates au format standard), dictionnaire des colonnes et "
                          "notebook Jupyter qui les lit ; ouvrez analyse.ipynb dans ce dossier.")
        archive.writestr("LISEZMOI.txt", "\n".join(lignes) + "\n")
    return tampon.getvalue()
