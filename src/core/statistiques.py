"""Transformations explicites et reproductibles, indépendantes de l'interface."""


from pandas.api.types import is_bool_dtype, is_numeric_dtype


def duplicate_rows(data):
    """Lignes strictement identiques en excès (la première occurrence n'est pas comptée)."""
    return int(data.duplicated().sum())


def numeric_columns(data):
    return [c for c in data if is_numeric_dtype(data[c]) and not is_bool_dtype(data[c])]


def tukey_bounds(values):
    """Bornes de Tukey (Q1 − 1,5 × IQR, Q3 + 1,5 × IQR) : au-delà, une valeur est inhabituelle, pas fausse."""
    q1, q3 = values.quantile([.25, .75])
    return q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
