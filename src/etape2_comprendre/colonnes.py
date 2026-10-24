"""Étape 2 (Comprendre) : une fiche lisible par colonne, pour un analyste débutant.

Entrées : données brutes, dictionnaire (rôle de chaque colonne, codes déclarés manquants),
ordre jour/mois choisi pour les dates. Sortie : une fiche par colonne (rôle en mots simples,
remplissage, aperçu des valeurs). Rien n'est modifié.
Limites : une colonne au rôle « Nombre » qui contient du texte est résumée sur ses seules
valeurs numériques ; les dates sont lues avec un seul format par colonne.
"""
import numpy as np
import pandas as pd

from src.config import CATEGORIES_RESUME
from src.core.dates import compter_par_periode, parse_dates
from src.core.dictionnaire import initial_dictionary, normalize_missing, records
from src.etape2_comprendre.diagnostic import diagnose

LIBELLES_ROLES = {"Identifiant": "Identifiant", "Catégorie": "Catégorie", "Mesure": "Nombre", "Date": "Date"}
PHRASES_ROLES = {
    "Identifiant": "Sert à reconnaître chaque ligne. On ne fait pas de calcul dessus.",
    "Catégorie": "Regroupe les lignes en familles. On compte combien il y en a dans chaque famille.",
    "Mesure": "Une quantité : on peut calculer une moyenne, un minimum, un maximum.",
    "Date": "Permet de suivre une évolution dans le temps.",
}


def resume_colonne(series, role, dayfirst=False):
    """Fiche d'une colonne déjà normalisée (codes manquants déclarés devenus vides).

    Retourne un dictionnaire : `colonne`, `role`, `libelle`, `phrase`, `remplies`, `total`,
    `distinctes`, puis des clés propres au rôle (voir les branches ci-dessous).
    """
    fiche = {"colonne": series.name, "role": role, "libelle": LIBELLES_ROLES[role], "phrase": PHRASES_ROLES[role],
             "remplies": int(series.notna().sum()), "total": len(series), "distinctes": int(series.nunique())}
    if role == "Identifiant":
        counts = series.value_counts()
        repeated = counts[counts > 1]
        fiche["repetees"] = len(repeated)
        fiche["exemple_repete"] = (str(repeated.index[0]), int(repeated.iloc[0])) if len(repeated) else None
    elif role == "Catégorie":
        counts = series.astype("string").value_counts()
        fiche["frequences"] = [(str(k), int(v)) for k, v in counts.head(CATEGORIES_RESUME).items()]
        fiche["autres"] = int(counts.iloc[CATEGORIES_RESUME:].sum())
    elif role == "Mesure":
        numbers = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        fiche["nombres"] = len(numbers)
        fiche["non_numeriques"] = fiche["remplies"] - len(numbers)
        if len(numbers):
            fiche.update(minimum=float(numbers.min()), mediane=float(numbers.median()),
                         moyenne=float(numbers.mean()), maximum=float(numbers.max()))
    else:
        dates = parse_dates(series, dayfirst).dropna()
        fiche["lisibles"] = len(dates)
        fiche["illisibles"] = fiche["remplies"] - len(dates)
        if len(dates):
            fiche["debut"], fiche["fin"] = dates.min(), dates.max()
            periodes, fiche["unite"] = compter_par_periode(dates)
            fiche["periodes"] = list(periodes.itertuples(index=False, name=None))
    return fiche


def resume_colonnes(raw, dictionary, dayfirst=None):
    """Une fiche par colonne du dictionnaire. `dayfirst` : colonne → jour d'abord (booléen)."""
    normalized = normalize_missing(raw, dictionary)
    dayfirst = dayfirst or {}
    return [resume_colonne(normalized[d["Colonne"]], d["Rôle"], dayfirst.get(d["Colonne"], False)) for d in dictionary]


def proposer_roles(dictionary, numeric_hints):
    """Propose « Mesure » pour une colonne lue comme texte mais surtout composée de nombres.

    Simple proposition affichée à l'utilisateur, qui peut la changer ; le type n'est pas converti.
    """
    surtout_numeriques = set(numeric_hints["Colonne"])
    for d in dictionary:
        if d["Colonne"] in surtout_numeriques and d["Rôle"] == "Catégorie":
            d["Rôle"] = "Mesure"
    return dictionary


def dictionnaire_propose(raw):
    """Dictionnaire de départ : rôles proposés à partir des noms et des valeurs, tous modifiables."""
    dictionary = records(initial_dictionary(raw))
    return proposer_roles(dictionary, diagnose(raw, dictionary, ignore_markers=True)["numeric_hints"])
