"""Étape 4 (Exporter) : fichiers remis à la fin de l'audit qualité, avant l'analyse métier.

Entrées : fichier d'origine (octets), données corrigées, lignes écartées, choix et journal.
Sorties : CSV lisibles, rapport qualité en Markdown et archive ZIP du projet.
Le fichier d'origine est recopié tel quel. Le rapport décrit ce qui a été vérifié et décidé ;
il ne certifie pas l'exactitude des valeurs.
"""
import io
import json
import zipfile
from datetime import datetime, timezone

import pandas as pd

from src.core.texte import nombre_lisible, pluriel
from src.etape3_corriger.correction import motif_lisible

LIMITES = ("Les vérifications portent sur la forme des données : codes de valeur manquante, textes dans des "
           "nombres, cases vides, lignes identiques et ordre des dates. Elles ne prouvent pas que les valeurs "
           "sont exactes, ni qu'elles répondent à la question métier.")


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


def rapport_qualite(nom_fichier, dimensions, empreinte, decisions, journal, resultat, notes="", regles_verifiees=None):
    """Rapport en Markdown : le fichier, les points vérifiés et décisions, ce qui a été fait, le résultat, les limites.

    `regles_verifiees` (mode expert) : règle → numéros des lignes qui ne la respectent pas.
    """
    lignes, colonnes = dimensions
    texte = [f"# Rapport qualité — {nom_fichier}", "",
             f"Produit le {datetime.now(timezone.utc):%d/%m/%Y à %H:%M} (UTC).", "",
             "## Le fichier", "",
             f"- {nombre_lisible(lignes)} lignes, {nombre_lisible(colonnes)} colonnes.",
             f"- Empreinte SHA-256 du fichier d'origine : `{empreinte}`. Ce fichier n'a pas été modifié.", "",
             "## Points vérifiés et décisions", ""]
    texte += [f"- {d['texte']} → **{d['choix']}**" for d in decisions] or ["- Aucun point à vérifier n'a été repéré."]
    texte += ["", "## Ce qui a été fait", ""] + [f"- {phrase}" for phrase in journal]
    texte += ["", "## Résultat", "",
              f"- Lignes gardées : {nombre_lisible(resultat['gardees'])} sur {nombre_lisible(resultat['total'])}.",
              f"- Lignes écartées : {nombre_lisible(resultat['ecartees'])}"
              + (" (" + ", ".join(f"{motif} : {nombre_lisible(n)}" for motif, n in resultat["motifs"]) + ")." if resultat["motifs"] else "."),
              f"- Cases vides : {nombre_lisible(resultat['vides_avant'])} avant, {nombre_lisible(resultat['vides_apres'])} après."]
    for m in resultat["moyennes"]:
        avant = nombre_lisible(m["avant"]) if m["avant"] is not None else "—"
        apres = nombre_lisible(m["apres"]) if m["apres"] is not None else "—"
        texte.append(f"- Moyenne de {m['colonne']} : {avant} avant ({nombre_lisible(m['n_avant'])} valeurs), "
                     f"{apres} après ({nombre_lisible(m['n_apres'])} valeurs).")
    if resultat["ecartees"]:
        texte += ["", "Les lignes écartées ne sont pas effacées : elles sont dans le fichier des lignes écartées, avec leur raison. "
                      "Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé."]
    if regles_verifiees:
        texte += ["", "## Règles vérifiées (mode expert)", ""]
        texte += [f"- {regle} : " + (f"{pluriel(len(n), 'ligne ne respecte pas', 'lignes ne respectent pas')}" if n
                                    else "respectée par toutes les lignes") for regle, n in regles_verifiees.items()]
        texte.append("Une règle non respectée n'est pas forcément une erreur : elle signale un écart avec ce qui était attendu.")
    texte += ["", "## Ce que ce rapport ne garantit pas", "", LIMITES]
    if notes.strip():
        texte += ["", "## Notes", "", notes.strip()]
    return "\n".join(texte) + "\n"


def archive_projet(source, nom_fichier, cleaned, rejects, rapport, choix, journal_moteur, dictionnaire):
    """Archive ZIP : fichier d'origine inchangé, données corrigées, lignes écartées, rapport et journal détaillé."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"fichier_origine/{nom_fichier}", source)
        archive.writestr("donnees_corrigees.csv", csv_bytes(cleaned))
        archive.writestr("lignes_ecartees.csv", csv_bytes(rejets_lisibles(rejects)))
        archive.writestr("rapport_qualite.md", rapport)
        archive.writestr("journal.json", json.dumps({"choix": choix, "journal": journal_moteur, "dictionnaire": dictionnaire},
                                                    ensure_ascii=False, indent=2, default=str))
        archive.writestr("LISEZMOI.txt", "Audit qualité d'un fichier CSV avant analyse métier.\n"
                                         "rapport_qualite.md : ce qui a été vérifié, décidé et fait.\n"
                                         "lignes_ecartees.csv : lignes mises de côté, avec leur numéro d'origine et leur raison.\n"
                                         "fichier_origine/ : le fichier importé, inchangé.\n")
    return tampon.getvalue()
