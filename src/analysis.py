"""Transformations explicites et reproductibles, indépendantes de l'interface."""
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype


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


def clean(data, rules):
    """Remplacements choisis par colonne, calculés sur les lignes reçues.

    Les espaces, doublons et suppressions de lignes sont traités par pipeline() (mises en rejet).
    """
    result = data.copy(deep=True)
    log = []
    for col, rule in rules.items():
        count = int(data[col].isna().sum())
        if rule in ("Conserver", "Supprimer les lignes") or not count:
            continue
        if rule in ("Moyenne", "Médiane"):
            if col not in numeric_columns(data):
                raise ValueError(f"{col} : remplacement numérique impossible.")
            value = data[col].mean() if rule == "Moyenne" else data[col].median()
            if pd.isna(value):
                raise ValueError(f"{col} : aucune valeur pour calculer le remplacement.")
            result[col] = result[col].astype(float).fillna(value)
        elif rule == "Inconnu":
            result[col] = result[col].astype("string").fillna("Inconnu")
        else:
            raise ValueError(f"Règle inconnue : {rule}")
        log.append({"Colonne": col, "Action": rule, "Cellules concernées": count})
    return result, log
