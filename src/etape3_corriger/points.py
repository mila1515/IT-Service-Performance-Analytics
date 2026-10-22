"""Étape 3 (Corriger) : points à vérifier, choix de l'utilisateur et résultat en mots simples.

Entrées : données brutes, dictionnaire (rôles), choix faits sur chaque point.
Sorties : la liste des points (cartes à afficher), le plan de nettoyage passé à `pipeline`,
le résumé du résultat et le journal en phrases.
Par défaut, chaque choix laisse les données inchangées : rien n'est corrigé sans décision.
Limites : cinq familles de points (codes de valeur manquante, texte dans des nombres, cases
vides, lignes identiques, dates ambiguës) ; aucune règle métier n'est déduite.
"""
from copy import deepcopy

import numpy as np
import pandas as pd

from src.core.dates import parse_dates
from src.core.dictionnaire import convert, normalize_missing
from src.core.statistiques import duplicate_rows, numeric_columns
from src.core.texte import nombre_lisible, pluriel

OPTIONS = {
    "marqueurs": [("manquant", "C'est une valeur manquante", "Le code devient une case vide"),
                  ("garder", "Garder tel quel", "Aucun changement")],
    "texte": [("nombres", "Traiter comme des nombres", "Le texte devient une case vide, la ligne est gardée"),
              ("ecarter", "Écarter ces lignes", "Elles sont mises de côté, avec la raison"),
              ("garder", "Ne rien changer", "La colonne reste du texte : aucun calcul possible")],
    "doublons": [("garder", "Garder toutes les lignes", "Ce sont de vraies lignes"),
                 ("une", "Garder une seule ligne", "Les copies sont mises de côté, avec la raison")],
    "dates": [("jour", "Jour d'abord", "05/03 = 5 mars"),
              ("mois", "Mois d'abord", "05/03 = 3 mai")],
}
DEFAUTS = {"marqueurs": "garder", "texte": "garder", "vides": "laisser", "doublons": "garder"}
TITRES = {
    "marqueurs": ("Des codes ressemblent à des valeurs manquantes",
                  "« ? », « NA » ou « inconnu » servent souvent à dire « pas d'information ». S'ils restent des valeurs, "
                  "ils comptent comme une vraie catégorie et faussent les comptages."),
    "texte": ("Du texte dans des colonnes de nombres",
              "Un texte au milieu de nombres empêche les calculs (moyenne, total…). C'est souvent une erreur de saisie."),
    "vides": ("Des cases vides",
              "Une case vide n'est pas un zéro. Les calculs l'ignorent simplement : ce n'est pas forcément un problème."),
    "doublons": ("Des lignes identiques",
                 "Deux lignes identiques peuvent être une saisie en double… ou deux vraies lignes pareilles. "
                 "Vous seul pouvez le savoir."),
    "dates": ("Des dates à lire dans le bon ordre",
              "« 05/03 » peut vouloir dire 5 mars ou 3 mai. Il faut choisir un seul sens pour toute la colonne."),
}
REGLES_VIDES = {"laisser": "Conserver", "mediane": "Médiane", "inconnu": "Inconnu", "ecarter": "Supprimer les lignes"}


def plan_nettoyage(dictionary, choix, suspects):
    """Traduit les choix en paramètres de `pipeline`, sans toucher au dictionnaire reçu.

    `suspects` : tableau des codes repérés par `diagnose` (colonnes « Colonne », « Valeur à vérifier »).
    Retourne {dictionary, missing_rules, deduplicate, conversion_policies}.
    """
    dico = deepcopy(dictionary)
    par_colonne = {d["Colonne"]: d for d in dico}
    for code, decision in choix.get("marqueurs", {}).items():
        if decision != "manquant":
            continue
        for col in suspects.loc[suspects["Valeur à vérifier"] == code, "Colonne"]:
            existants = [v for v in par_colonne[col]["Marqueurs vides"].splitlines() if v.strip()]
            par_colonne[col]["Marqueurs vides"] = "\n".join(dict.fromkeys(existants + [code]))
    politiques = {}
    for col, decision in choix.get("texte", {}).items():
        if decision in ("nombres", "ecarter"):
            par_colonne[col].update({"Type attendu": "Nombre", "Rôle": "Mesure"})
            politiques[col] = "Convertir en vide" if decision == "nombres" else "Mettre en rejet"
    regles = {col: REGLES_VIDES[decision] for col, decision in choix.get("vides", {}).items()}
    return {"dictionary": dico, "missing_rules": regles,
            "deduplicate": choix.get("doublons", {}).get("doublons") == "une", "conversion_policies": politiques}


def _point_marqueurs(suspects):
    lignes = []
    for code, groupe in suspects.groupby("Valeur à vérifier", sort=False):
        colonnes = groupe["Colonne"].tolist()
        noms = ", ".join(map(str, colonnes[:5])) + (" …" if len(colonnes) > 5 else "")
        lignes.append({"cle": code, "texte": f"« {code} » : {pluriel(int(groupe['Occurrences'].sum()), 'case')} "
                                              f"dans {pluriel(len(colonnes), 'colonne')} ({noms})",
                       "options": OPTIONS["marqueurs"], "defaut": DEFAUTS["marqueurs"]})
    return lignes


def _point_texte(hints):
    return [{"cle": row["Colonne"],
             "texte": f"{row['Colonne']} : {pluriel(row['Valeurs non numériques'], 'valeur non numérique', 'valeurs non numériques')} "
                      f"parmi {nombre_lisible(row['Valeurs renseignées'])} (ex. : {row['Exemples non numériques']})",
             "options": OPTIONS["texte"], "defaut": DEFAUTS["texte"]} for _, row in hints.iterrows()]


def _point_vides(raw, dictionary, plan):
    """Cases vides après les choix déjà faits (codes reconnus, textes devenus vides)."""
    normalized = normalize_missing(raw, plan["dictionary"])
    roles = {d["Colonne"]: d for d in plan["dictionary"]}
    lignes = []
    for d in dictionary:
        col = d["Colonne"]
        definition = roles[col]
        values = convert(normalized[col], definition["Type attendu"], definition["Format date"])
        manquants = values.isna()
        if plan["conversion_policies"].get(col) == "Mettre en rejet":
            manquants &= normalized[col].isna()
        count = int(manquants.sum())
        if not count:
            continue
        numerique = col in numeric_columns(values.to_frame())
        options = [("laisser", "Laisser vide", "Les calculs se font sur les autres valeurs")]
        nombres = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna() if numerique else []
        if numerique and definition["Rôle"] == "Mesure" and len(nombres):
            options.append(("mediane", "Remplacer par la médiane",
                            f"Une estimation : la valeur du milieu (actuellement {nombre_lisible(float(nombres.median()))})"))
        if definition["Rôle"] == "Catégorie" and not numerique:
            options.append(("inconnu", "Remplacer par « Inconnu »", "Ces lignes restent visibles dans les comptages"))
        options.append(("ecarter", "Écarter ces lignes", "Elles sont mises de côté, avec la raison"))
        lignes.append({"cle": col, "texte": f"{col} : {pluriel(count, 'case vide', 'cases vides')} "
                                             f"({nombre_lisible(round(count / len(raw) * 100, 1))} %)",
                       "options": options, "defaut": DEFAUTS["vides"]})
    return lignes


def _point_doublons(raw):
    count = duplicate_rows(raw)
    if not count:
        return []
    copies = raw.duplicated(keep="first")
    premiere = int(np.flatnonzero(copies.to_numpy())[0])
    origine = int(np.flatnonzero(raw.eq(raw.iloc[premiere]).all(axis=1).to_numpy())[0])
    texte = f"{pluriel(count, 'ligne identique', 'lignes identiques')} à une autre (ex. : ligne {premiere + 1} = ligne {origine + 1})"
    return [{"cle": "doublons", "texte": texte, "options": OPTIONS["doublons"], "defaut": DEFAUTS["doublons"]}]


def _point_dates(normalized, dictionary):
    lignes = []
    for d in dictionary:
        col = d["Colonne"]
        series = normalized[col]
        if d["Rôle"] != "Date" or pd.api.types.is_datetime64_any_dtype(series) or series.notna().sum() == 0:
            continue
        lues = {cle: parse_dates(series, cle == "jour") for cle in ("jour", "mois")}
        illisibles = {cle: int((series.notna() & dates.isna()).sum()) for cle, dates in lues.items()}
        # Rien à décider si les deux lectures donnent les mêmes dates (ex. format ISO 2026-03-05).
        if lues["jour"].equals(lues["mois"]):
            continue
        defaut = "mois" if illisibles["mois"] < illisibles["jour"] else "jour"
        exemple = str(series.dropna().iloc[0])
        texte = (f"{col} : exemple « {exemple} » — jour d'abord : {pluriel(illisibles['jour'], 'date illisible', 'dates illisibles')}, "
                 f"mois d'abord : {pluriel(illisibles['mois'], 'date illisible', 'dates illisibles')}")
        lignes.append({"cle": col, "texte": texte, "options": OPTIONS["dates"], "defaut": defaut})
    return lignes


def detecter_points(raw, dictionary, choix, diagnostic):
    """Cartes à afficher, dans l'ordre du parcours. `diagnostic` : résultat de `diagnose(..., ignore_markers=True)`.

    Chaque carte : {type, titre, pourquoi, lignes}, chaque ligne : {cle, texte, options, defaut}.
    Les cases vides tiennent compte des choix déjà faits sur les codes et les textes.
    """
    plan = plan_nettoyage(dictionary, choix, diagnostic["suspects"])
    familles = {
        "marqueurs": _point_marqueurs(diagnostic["suspects"]),
        "texte": _point_texte(diagnostic["numeric_hints"]),
        "vides": _point_vides(raw, dictionary, plan),
        "doublons": _point_doublons(raw),
        "dates": _point_dates(diagnostic["normalized"], dictionary),
    }
    return [{"type": t, "titre": TITRES[t][0], "pourquoi": TITRES[t][1], "lignes": lignes}
            for t, lignes in familles.items() if lignes]


def decisions(points, choix):
    """Pour le rapport : chaque point affiché, avec le libellé de l'option retenue (défaut si aucun choix)."""
    lignes = []
    for point in points:
        for ligne in point["lignes"]:
            cle = choix.get(point["type"], {}).get(ligne["cle"], ligne["defaut"])
            libelle = next(label for key, label, _ in ligne["options"] if key == cle)
            lignes.append({"titre": point["titre"], "texte": ligne["texte"], "choix": libelle})
    return lignes


def motif_lisible(motif):
    """Motif de rejet du moteur → phrase simple."""
    if motif.startswith("Valeur manquante : "):
        return f"{motif.removeprefix('Valeur manquante : ')} vide"
    if motif.startswith("Conversion impossible : "):
        return f"{motif.removeprefix('Conversion impossible : ').split(' → ')[0]} : texte au lieu d'un nombre"
    if motif == "Doublon strict après transformations":
        return "copie identique d'une autre ligne"
    return motif


def resume_resultat(raw, plan, cleaned, rejects):
    """Chiffres avant / après pour l'encadré « Résultat de vos choix ».

    Les cases vides « avant » sont comptées avec les mêmes codes manquants que « après ».
    Les moyennes ne portent que sur les colonnes numériques au rôle Mesure.
    """
    normalized = normalize_missing(raw, plan["dictionary"])
    motifs = rejects[("Traçabilité", "Motifs")].str.split(" ; ").explode() if len(rejects) else pd.Series(dtype=str)
    moyennes = []
    mesures = [d["Colonne"] for d in plan["dictionary"] if d["Rôle"] == "Mesure"]
    for col in [c for c in mesures if c in numeric_columns(cleaned)]:
        avant = pd.to_numeric(normalized[col], errors="coerce").dropna()
        apres = cleaned[col].dropna()
        if len(avant) or len(apres):
            moyennes.append({"colonne": col, "avant": float(avant.mean()) if len(avant) else None, "n_avant": len(avant),
                             "apres": float(apres.mean()) if len(apres) else None, "n_apres": len(apres)})
    return {"total": len(raw), "gardees": len(cleaned), "ecartees": len(rejects),
            "vides_avant": int(normalized.isna().sum().sum()), "vides_apres": int(cleaned.isna().sum().sum()),
            "motifs": [(motif_lisible(m), int(n)) for m, n in motifs.value_counts().items()],
            "moyennes": moyennes}


def phrases_journal(log):
    """Entrées du journal du moteur → phrases simples, dans l'ordre."""
    phrases = []
    for entry in log:
        action, col, n = entry["Action"], entry["Colonne"], entry["Cellules / lignes"]
        if action == "Marqueurs vides normalisés":
            phrases.append(f"{col} : {pluriel(n, 'code reconnu', 'codes reconnus')} comme valeur manquante")
        elif action == "Conversions impossibles : Convertir en vide":
            phrases.append(f"{col} : {pluriel(n, 'texte devenu', 'textes devenus')} une case vide")
        elif action in ("Médiane", "Moyenne"):
            phrases.append(f"{col} : {pluriel(n, 'case vide remplacée', 'cases vides remplacées')} par la {action.lower()}")
        elif action == "Inconnu":
            phrases.append(f"{col} : {pluriel(n, 'case vide remplacée', 'cases vides remplacées')} par « Inconnu »")
        elif action.startswith("Mise en rejet : "):
            phrases.append(f"{pluriel(n, 'ligne mise', 'lignes mises')} de côté : {motif_lisible(action.removeprefix('Mise en rejet : '))}")
        elif action.startswith("Conversion en "):
            phrases.append(f"{col} : traitée comme des nombres")
    return phrases or ["Aucun changement : les données restent telles qu'importées."]
