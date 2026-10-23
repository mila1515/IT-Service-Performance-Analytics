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


def archive_projet(source, nom_fichier, cleaned, rejects, rapport, choix, journal_moteur, dictionnaire, rapport_html=None):
    """Archive ZIP : fichier d'origine inchangé, données corrigées, lignes écartées, rapports et journal détaillé."""
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
        archive.writestr("LISEZMOI.txt", "Audit qualité d'un fichier CSV avant analyse métier.\n"
                                         "rapport_qualite.html : le rapport complet avec les graphiques (à ouvrir dans le navigateur).\n"
                                         "rapport_qualite.md : le même rapport en texte.\n"
                                         "lignes_ecartees.csv : lignes mises de côté, avec leur numéro d'origine et leur raison.\n"
                                         "fichier_origine/ : le fichier importé, inchangé.\n")
    return tampon.getvalue()
