"""Dictionnaire des colonnes : types attendus, marqueurs vides et conversions (commun à toutes les étapes)."""


import json

import numpy as np
import pandas as pd

from src.core.roles import infer_roles

def initial_dictionary(data):
    roles = infer_roles(data)
    return pd.DataFrame([{"Colonne": col, "Définition": "", "Type observé": str(data[col].dtype),
                          "Type attendu": "Conserver", "Rôle": roles[col], "Unité": "",
                          "Obligatoire": False, "Unique": False, "Critique": False,
                          "Marqueurs vides": "", "Format date": ""} for col in data])


def normalize_missing(data, dictionary):
    result = data.copy(deep=True)
    for d in dictionary:
        col = d["Colonne"]
        markers = [v.strip() for v in d["Marqueurs vides"].splitlines() if v.strip()]
        # Les cellules composées d'espaces sont vides ; les autres marqueurs sont explicites.
        # Test sur les valeurs distinctes : même résultat, coût réduit sur les gros fichiers.
        uniques = pd.Series(result[col].dropna().unique(), dtype=object)
        text = uniques.astype("string").str.strip()
        blanks = uniques[(text.eq("") | text.isin(markers)).fillna(False).to_numpy()]
        if len(blanks):
            result[col] = result[col].mask(result[col].isin(blanks.tolist()))
    return result


def convert(series, target, date_format=""):
    if target == "Nombre":
        return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    if target == "Date":
        return pd.to_datetime(series, format=date_format or "ISO8601", errors="coerce", utc=True).dt.tz_convert(None)
    if target == "Texte":
        return series.astype("string")
    return series.copy()


def records(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso", force_ascii=False))
