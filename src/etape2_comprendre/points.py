"""Étape 2 (Comprendre) : repérer les points à vérifier avant toute correction.

Entrées : données brutes, dictionnaire (rôles), diagnostic (`diagnose(..., ignore_markers=True)`) et
choix déjà faits à l'étape 3 (les cases vides en dépendent). Sortie : une carte par famille de points,
chaque ligne avec ses options et une valeur par défaut qui ne change rien aux données.
Limites : cinq familles (codes de valeur manquante, texte dans des nombres, cases vides, lignes
identiques, dates ambiguës) ; aucune règle métier n'est déduite.
"""
from copy import deepcopy

import numpy as np
import pandas as pd

from src.config import MARQUEURS_POSSIBLES
from src.core.dates import parse_dates
from src.core.dictionnaire import convert, normalize_missing
from src.core.regles import audit
from src.core.statistiques import duplicate_rows, numeric_columns
from src.core.texte import nombre_lisible, pluriel


OPTIONS = {
    "marqueurs": [("manquant", "C'est une valeur manquante", "Le code devient une case vide"),
                  ("garder", "Garder tel quel", "Aucun changement")],
    "texte": [("nombres", "Traiter comme des nombres", "Le texte devient une case vide, la ligne est gardée"),
              ("ecarter", "Écarter ces lignes", "Elles sont mises de côté, avec la raison"),
              ("garder", "Ne rien changer", "Le texte reste dans les données ; les graphiques ne compteront que les nombres")],
    "doublons": [("garder", "Garder toutes les lignes", "Ce sont de vraies lignes"),
                 ("une", "Garder une seule ligne", "Les copies sont mises de côté, avec la raison")],
    "dates": [("jour", "Jour d'abord", "05/03 = 5 mars"),
              ("mois", "Mois d'abord", "05/03 = 3 mai")],
    # Mode expert léger.
    "regles": [("garder", "Garder et signaler", "Les lignes restent ; le rapport le mentionne"),
               ("ecarter", "Écarter ces lignes", "Elles sont mises de côté, avec la raison")],
    "espaces": [("garder", "Laisser tel quel", "Aucun changement"),
                ("supprimer", "Supprimer les espaces en trop", "Au début et à la fin des textes")],
}


DEFAUTS = {"marqueurs": "garder", "texte": "garder", "vides": "laisser", "doublons": "garder",
           "regles": "garder", "espaces": "garder"}


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
    "regles": ("Règles non respectées",
               "Ce sont les règles cochées à l'étape Comprendre. Une ligne qui ne les respecte pas n'est pas forcément "
               "fausse : vérifiez-la avant de l'écarter."),
    "espaces": ("Espaces en trop",
                "« A » et « A » suivi d'un espace sont comptés comme deux valeurs différentes. Supprimer les espaces "
                "au début et à la fin des textes évite ce piège."),
}


def dictionnaire_selon_choix(dictionary, choix, suspects):
    """Copie du dictionnaire après les choix sur les codes manquants et les textes dans des nombres.

    `suspects` : tableau des codes repérés par `diagnose` (colonnes « Colonne », « Valeur à vérifier »).
    Retourne (dictionnaire, politiques de conversion par colonne). Le dictionnaire reçu n'est pas modifié.
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
    return dico, politiques


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


def _point_vides(raw, dictionary, dico, politiques):
    """Cases vides après les choix déjà faits (codes reconnus, textes devenus vides)."""
    normalized = normalize_missing(raw, dico)
    roles = {d["Colonne"]: d for d in dico}
    lignes = []
    for d in dictionary:
        col = d["Colonne"]
        definition = roles[col]
        values = convert(normalized[col], definition["Type attendu"], definition["Format date"])
        manquants = values.isna()
        if politiques.get(col) == "Mettre en rejet":
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


def verifier_regles(raw, dico, controles):
    """Pour chaque contrôle (`regles_simples`), les numéros de ligne (à partir de 1) qui ne le respectent pas."""
    if not controles:
        return {}
    _, details = audit(raw, dico, controles)
    return {c["id"]: sorted(int(n) for n in details.loc[details["ID règle"] == c["id"], "Enregistrement source"])
            for c in controles}


def _point_regles(resultats):
    lignes = []
    for regle, numeros in resultats.items():
        if numeros:
            exemple = ", ".join(map(str, numeros[:5])) + (" …" if len(numeros) > 5 else "")
            texte = (f"{regle} — {pluriel(len(numeros), 'ligne ne respecte pas', 'lignes ne respectent pas')} "
                     f"({'ligne' if len(numeros) == 1 else 'lignes'} {exemple})")
            lignes.append({"cle": regle, "texte": texte, "options": OPTIONS["regles"], "defaut": DEFAUTS["regles"],
                           "numeros": numeros})
    return lignes


def _avec_espaces(series):
    """Masque des textes avec un espace au début ou à la fin (les cases d'espaces seuls sont déjà vides)."""
    texte = series.astype("string")
    nettoye = texte.str.strip()
    return (texte.ne(nettoye) & nettoye.ne("")).fillna(False)


def compter_espaces(raw):
    """Nombre de textes avec des espaces en trop, toutes colonnes de texte confondues."""
    total = 0
    for col in raw.select_dtypes(include=["object", "string"]):
        # Test sur les valeurs distinctes : rapide sur les gros fichiers.
        effectifs = raw[col].value_counts()
        total += int(effectifs[_avec_espaces(effectifs.index.to_series()).to_numpy()].sum())
    return total


def _point_espaces(raw):
    nombre = compter_espaces(raw)
    if not nombre:
        return []
    return [{"cle": "espaces", "texte": f"{pluriel(nombre, 'valeur')} avec des espaces au début ou à la fin",
             "options": OPTIONS["espaces"], "defaut": DEFAUTS["espaces"]}]


def detecter_points(raw, dictionary, choix, diagnostic, controles=None, expert=False):
    """Cartes à afficher, dans l'ordre du parcours. `diagnostic` : résultat de `diagnose(..., ignore_markers=True)`.

    Chaque carte : {type, titre, pourquoi, lignes}, chaque ligne : {cle, texte, options, defaut}.
    Les cases vides tiennent compte des choix déjà faits sur les codes et les textes.
    Mode expert : règles non respectées (`controles`, voir `regles_simples`) et espaces en trop.
    """
    dico, politiques = dictionnaire_selon_choix(dictionary, choix, diagnostic["suspects"])
    familles = {
        "marqueurs": _point_marqueurs(diagnostic["suspects"]),
        "texte": _point_texte(diagnostic["numeric_hints"]),
        "vides": _point_vides(raw, dictionary, dico, politiques),
        "doublons": _point_doublons(raw),
        "dates": _point_dates(diagnostic["normalized"], dictionary),
    }
    if expert:
        familles["regles"] = _point_regles(verifier_regles(raw, dico, controles or []))
        familles["espaces"] = _point_espaces(raw)
    return [{"type": t, "titre": TITRES[t][0], "pourquoi": TITRES[t][1], "lignes": lignes}
            for t, lignes in familles.items() if lignes]


def exemples(raw, diagnostic, type_, cle, limite=5, numeros=None):
    """Quelques lignes concernées par un point, numérotées comme dans le fichier (à partir de 1).

    `numeros` : pour une règle, les lignes qui ne la respectent pas (`verifier_regles`).
    """
    normalized = diagnostic["normalized"]
    if type_ == "marqueurs":
        suspects = diagnostic["suspects"]
        colonnes = suspects.loc[suspects["Valeur à vérifier"] == cle, "Colonne"].tolist()
        masque = raw[colonnes].astype("string").apply(lambda col: col.str.strip()).eq(cle).any(axis=1)
    elif type_ == "texte":
        valeurs = normalized[cle].astype("string").str.strip()
        masque = valeurs.notna() & pd.to_numeric(valeurs, errors="coerce").isna() & ~valeurs.str.casefold().isin(MARQUEURS_POSSIBLES)
    elif type_ == "vides":
        masque = normalized[cle].isna()
    elif type_ == "doublons":
        masque = raw.duplicated(keep=False)
    elif type_ == "regles":
        masque = pd.Series(raw.index.isin([n - 1 for n in numeros or []]), index=raw.index)
    elif type_ == "espaces":
        textes = raw.select_dtypes(include=["object", "string"])
        masque = textes.apply(_avec_espaces).any(axis=1) if len(textes.columns) else pd.Series(False, index=raw.index)
    else:
        masque = normalized[cle].notna()
    lignes = raw.loc[masque.fillna(False)].head(limite)
    return lignes.set_axis(lignes.index + 1).rename_axis("Ligne")
