"""Rôles proposés pour les colonnes (identifiant, catégorie, mesure, date), toujours corrigeables."""


import re

import pandas as pd

from src.core.statistiques import numeric_columns

ROLES = ["Mesure", "Catégorie", "Date", "Identifiant"]

# Mots du nom d'une colonne (français et anglais) qui suggèrent un rôle ; le rôle reste corrigeable.
ID_WORDS = {"id", "uuid", "code", "number", "num", "no", "n°", "numero", "numéro", "matricule",
            "identifiant", "ref", "réf", "reference", "référence", "cle", "clé"}

DATE_WORDS = {"horodatage", "timestamp", "datetime"}

ISO_DATE = r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$"


def looks_like_iso_dates(series, sample=500):
    """Toutes les valeurs distinctes observées (échantillon) ont la forme AAAA-MM-JJ[ hh:mm[:ss]][fuseau]."""
    values = pd.Series(series.dropna().unique()[:sample], dtype="string").str.strip()
    return bool(len(values)) and bool(values.str.fullmatch(ISO_DATE).all())


def infer_roles(data):
    roles = {}
    numbers = numeric_columns(data)
    for col in data:
        name = str(col).lower()
        words = set(re.split(r"(?:[^\w°]|_)+", name))
        if words & ID_WORDS:
            roles[col] = "Identifiant"
        elif pd.api.types.is_datetime64_any_dtype(data[col]):
            roles[col] = "Date"
        # « update » (updated_by…) n'indique pas une date.
        elif col not in numbers and ("date" in name.replace("update", "") or name.endswith("_at")
                                     or words & DATE_WORDS or looks_like_iso_dates(data[col])):
            roles[col] = "Date"
        else:
            roles[col] = "Mesure" if col in numbers else "Catégorie"
    return roles
