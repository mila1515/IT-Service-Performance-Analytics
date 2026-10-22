"""Étape 4 : préparation des colonnes pour les graphiques (dates, nombres), sans modifier les données."""


import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype
from pandas.tseries.api import guess_datetime_format


def parse_dates(series, dayfirst=False):
    """Un seul format par colonne : une cellule n'est jamais réinterprétée isolément."""
    if pd.api.types.is_datetime64_any_dtype(series):
        values = pd.to_datetime(series, utc=True)
    elif is_numeric_dtype(series) and not is_bool_dtype(series):
        # Un nombre est lu comme une année, jamais comme un horodatage en nanosecondes.
        whole = series.where(series.notna() & (series % 1 == 0))
        values = pd.to_datetime(whole.astype("Int64").astype("string"), format="%Y", errors="coerce", utc=True)
    else:
        # Conversion des valeurs distinctes seulement, puis report sur chaque ligne.
        codes, uniques = pd.factorize(series.astype("string").str.strip())
        text = pd.Series(uniques, dtype="string")
        parsed = pd.to_datetime(text, format="ISO8601", errors="coerce", utc=True)
        failed = text.notna() & parsed.isna()
        if failed.any():
            with warnings.catch_warnings():
                # Le format deviné est signalé à l'utilisateur via les conversions impossibles.
                warnings.simplefilter("ignore", UserWarning)
                guessed = guess_datetime_format(str(text[failed].iloc[0]), dayfirst=dayfirst)
            if guessed:
                parsed = pd.to_datetime(text, format=guessed, errors="coerce", utc=True)
        # Le code -1 (valeur manquante) pointe sur le NaT ajouté en dernière position.
        dates = parsed.dt.tz_convert(None).to_numpy()
        lookup = np.append(dates, np.array(["NaT"], dtype=dates.dtype))
        return pd.Series(lookup[codes], index=series.index, name=series.name)
    return values.dt.tz_convert(None)


def prepare(data, roles, dayfirst=False):
    """Copie pour la visualisation uniquement ; aucune correction du brut."""
    result = data.copy()
    invalid = {}
    for col, role in roles.items():
        if role == "Date":
            result[col] = parse_dates(data[col], dayfirst)
        elif role == "Mesure":
            result[col] = pd.to_numeric(data[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        else:
            result[col] = data[col].astype("string")
        count = int((data[col].notna() & result[col].isna()).sum())
        if count:
            invalid[col] = count
    return result, invalid
