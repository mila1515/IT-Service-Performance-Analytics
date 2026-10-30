"""Le résumé envoyé à l'IA : la forme du fichier et les problèmes repérés, jamais ses lignes.

Entrées : données brutes, dictionnaire, cartes de l'étape Corriger (`detecter_points`), diagnostic et fiches
(`resume_colonnes`). Sortie : le résumé et les références (identifiant de point → type et clé de la carte).
Les textes des cartes ne sont pas envoyés tels quels : ils peuvent citer des valeurs du fichier. Seuls les comptages
en sont repris. Les valeurs fréquentes, exemples et répartitions des fiches sont écartés de la même façon.
"""
from src.core.texte import nombre_lisible


def correspondance(dictionary, masquer):
    """Nom de colonne → nom envoyé : le nom réel, ou « Colonne 1, Colonne 2… » si `masquer`."""
    return {d["Colonne"]: f"Colonne {i}" if masquer else str(d["Colonne"]) for i, d in enumerate(dictionary, 1)}


def _masquer_texte(texte, noms):
    """Remplace les noms de colonnes dans le texte d'une règle (les plus longs d'abord)."""
    for colonne in sorted(noms, key=lambda c: len(str(c)), reverse=True):
        texte = texte.replace(str(colonne), noms[colonne])
    return texte


def _colonne_resumee(fiche, noms):
    colonne = {"nom": noms[fiche["colonne"]], "type": fiche["libelle"], "remplies": fiche["remplies"],
               "total": fiche["total"], "valeurs_differentes": fiche["distinctes"]}
    if fiche["role"] == "Identifiant":
        colonne["valeurs_repetees"] = fiche["repetees"]
    elif fiche["role"] == "Mesure":
        colonne["non_numeriques"] = fiche["non_numeriques"]
        if fiche["nombres"]:
            colonne.update({cle: nombre_lisible(fiche[cle]) for cle in ("minimum", "mediane", "moyenne", "maximum")})
    elif fiche["role"] == "Date":
        colonne["illisibles"] = fiche["illisibles"]
        if fiche["lisibles"]:
            colonne.update(debut=f"{fiche['debut']:%d/%m/%Y}", fin=f"{fiche['fin']:%d/%m/%Y}")
    return colonne


def _comptage(type_, ligne):
    """Le comptage d'une ligne de carte, sans le nom de la colonne ni les exemples qui suivent."""
    texte, cle = ligne["texte"], str(ligne["cle"])
    if type_ == "marqueurs":
        return texte[len(f"« {cle} » : "):].split(" (")[0]
    if type_ == "texte":
        return texte[len(f"{cle} : "):].split(" (ex. :")[0]
    if type_ == "vides":
        return texte[len(f"{cle} : "):]
    if type_ == "doublons":
        return texte.split(" à une autre")[0]
    if type_ == "dates":
        return texte.rsplit(" — ", 1)[-1]
    if type_ == "regles":
        return texte[len(f"{cle} — "):].split(" (")[0]
    return texte  # espaces : ne cite aucune valeur


def _cible(type_, ligne, noms, suspects):
    if type_ == "marqueurs":
        colonnes = suspects.loc[suspects["Valeur à vérifier"] == ligne["cle"], "Colonne"]
        return {"code": ligne["cle"], "colonnes": [noms[c] for c in colonnes]}
    if type_ in ("texte", "vides", "dates"):
        return {"colonne": noms[ligne["cle"]]}
    if type_ == "regles":
        return {"regle": _masquer_texte(str(ligne["cle"]), noms)}
    return {}


def construire_resume(raw, dictionary, points, diagnostic, fiches, masquer=False):
    """Retourne (résumé prêt à envoyer, références {identifiant: {type, cle}}, noms {colonne: nom envoyé})."""
    noms = correspondance(dictionary, masquer)
    envoyes, references = [], {}
    for point in points:
        for ligne in point["lignes"]:
            identifiant = f"P{len(references) + 1}"
            references[identifiant] = {"type": point["type"], "cle": ligne["cle"]}
            envoyes.append({"id": identifiant, "probleme": point["titre"],
                            **_cible(point["type"], ligne, noms, diagnostic["suspects"]),
                            "constat": _comptage(point["type"], ligne),
                            "choix_possibles": [{"cle": cle, "libelle": libelle} for cle, libelle, _ in ligne["options"]]})
    resume = {"fichier": {"lignes": len(raw), "colonnes": len(dictionary)},
              "colonnes": [_colonne_resumee(f, noms) for f in fiches], "points": envoyes}
    return resume, references, noms
