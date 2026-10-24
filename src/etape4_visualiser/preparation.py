"""Étape 4 : préparation des colonnes pour les graphiques (dates, nombres), sans modifier les données."""


import numpy as np
import pandas as pd

from src.core.dates import parse_dates


def prepare(data, roles, dayfirst=False):
    """Copie pour la visualisation uniquement ; aucune correction du brut.

    `dayfirst` : un booléen pour toutes les dates, ou un dictionnaire colonne → booléen.
    """
    result = data.copy()
    invalid = {}
    for col, role in roles.items():
        if role == "Date":
            result[col] = parse_dates(data[col], dayfirst.get(col, False) if isinstance(dayfirst, dict) else dayfirst)
        elif role == "Mesure":
            result[col] = pd.to_numeric(data[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        else:
            result[col] = data[col].astype("string")
        count = int((data[col].notna() & result[col].isna()).sum())
        if count:
            invalid[col] = count
    return result, invalid
