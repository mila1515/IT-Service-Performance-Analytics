"""Transformations explicites et reproductibles, indépendantes de l'interface."""


import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype


def profile(data):
    return pd.DataFrame({
        "Type": data.dtypes.astype(str),
        "Renseignées": data.notna().sum(),
        "Manquantes": data.isna().sum(),
        "Manquantes (%)": data.isna().mean().mul(100).round(2),
        "Valeurs distinctes": data.nunique(),
    })


def duplicate_rows(data):
    """Lignes strictement identiques en excès (la première occurrence n'est pas comptée)."""
    return int(data.duplicated().sum())


def numeric_columns(data):
    return [c for c in data if is_numeric_dtype(data[c]) and not is_bool_dtype(data[c])]


def statistics(data, exclude=()):
    """Les colonnes exclues (identifiants, dates numériques) ne sont pas des mesures."""
    columns = [c for c in numeric_columns(data) if c not in exclude]
    if not columns:
        return pd.DataFrame()
    result = data[columns].describe().T.rename(columns={
        "count": "Effectif", "mean": "Moyenne", "std": "Écart-type",
        "min": "Minimum", "25%": "Q1", "50%": "Médiane",
        "75%": "Q3", "max": "Maximum",
    })
    result["Variance"] = data[columns].var()
    return result


def tukey_bounds(values):
    """Bornes de Tukey (Q1 − 1,5 × IQR, Q3 + 1,5 × IQR) : au-delà, une valeur est inhabituelle, pas fausse."""
    q1, q3 = values.quantile([.25, .75])
    return q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
