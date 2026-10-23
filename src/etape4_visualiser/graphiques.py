"""Étape 4 : filtres du « Filtrage » (catégorie, période), sans dépendance à l'interface."""


import pandas as pd

def apply_filters(data, filters):
    result = data
    for spec in filters:
        col = spec["column"]
        values = result[col]
        if spec["type"] == "Catégorie":
            # Mode exclusion : les valeurs choisies sont retirées, les autres conservées.
            chosen = values.astype("string").isin(spec["values"])
            mask = values.notna() & (~chosen if spec.get("exclude", False) else chosen)
        elif spec["type"] == "Date":
            start = pd.Timestamp(spec["low"])
            end = pd.Timestamp(spec["high"]) + pd.Timedelta(days=1)
            mask = (values >= start) & (values < end)
        else:
            mask = values.between(spec["low"], spec["high"])
        if spec["missing"]:
            mask = mask | values.isna()
        result = result.loc[mask.fillna(False)]
    return result.copy()
