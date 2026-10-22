"""Suggestions, filtres et agrégations sans dépendance à l'interface."""


import itertools

import pandas as pd

KINDS = ["Histogramme", "Boîte à moustaches", "Barres", "Courbe", "Nuage de points", "Tableau croisé"]

AGGREGATIONS = {"Effectif": "size", "Somme": "sum", "Moyenne": "mean", "Médiane": "median"}

PERIODS = {"Jour": "D", "Mois": "MS", "Année": "YS"}


def suggestions(roles):
    measures = [c for c, r in roles.items() if r == "Mesure"]
    categories = [c for c, r in roles.items() if r == "Catégorie"]
    dates = [c for c, r in roles.items() if r == "Date"]
    result = []

    def add(kind, x, y=None, reason="", agg="Effectif"):
        result.append({"kind": kind, "x": x, "y": y, "agg": agg,
                       "title": f"{kind} · {x}" + (f" / {y}" if y else ""), "reason": reason,
                       "period": "Mois", "sort": "Valeur décroissante", "limit": 20,
                       "width": "Demi", "filters": []})

    for col in measures:
        add("Histogramme", col, reason="Examiner la distribution d'une mesure numérique.")
        add("Boîte à moustaches", col, reason="Repérer la dispersion et les valeurs extrêmes, sans les supprimer.")
    for col in categories:
        add("Barres", col, reason="Comparer les effectifs des catégories.")
        for measure in measures[:3]:
            add("Barres", col, measure, "Comparer une mesure entre groupes ; confirmez le calcul métier.", "Médiane")
    for date in dates:
        add("Courbe", date, reason="Suivre le volume dans le temps après confirmation du format des dates.")
        for measure in measures[:3]:
            add("Courbe", date, measure, "Observer l'évolution d'une mesure dans le temps.", "Moyenne")
    for x, y in itertools.islice(itertools.combinations(measures, 2), 10):
        add("Nuage de points", x, y, "Explorer une relation entre deux mesures ; corrélation ne signifie pas causalité.")
    for x, y in itertools.islice(itertools.combinations(categories, 2), 10):
        add("Tableau croisé", x, y, "Comparer les effectifs de deux dimensions catégorielles.")
    return result


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


def chart_data(data, spec):
    """Retourne les données tracées et la quantité de lignes non exploitables."""
    kind, x, y, agg = (spec[k] for k in ("kind", "x", "y", "agg"))
    needed = [x] + ([y] if y and (kind in ("Nuage de points", "Tableau croisé") or agg != "Effectif") else [])
    valid = data.dropna(subset=list(dict.fromkeys(needed)))
    excluded = len(data) - len(valid)
    if valid.empty:
        return pd.DataFrame(), excluded
    if kind in ("Histogramme", "Boîte à moustaches"):
        return valid[[x]].rename(columns={x: "Valeur"}), excluded
    if kind == "Nuage de points":
        return pd.DataFrame({"X": valid[x], "Y": valid[y]}), excluded
    if kind == "Tableau croisé":
        # Évite de construire une matrice N×N pour des colonnes à forte cardinalité.
        # Index nommé avant reset_index : aucune collision avec une colonne « Valeur ».
        grouped = valid.groupby([x, y], observed=True).size().rename_axis(["Groupe", "Série"]).rename("Valeur").reset_index()
        return grouped, excluded
    if kind == "Courbe":
        indexed = valid.set_index(x).sort_index()
        groups = indexed.resample(PERIODS[spec["period"]])
    else:
        groups = valid.groupby(x, observed=True, sort=True)
    if agg == "Effectif":
        values = groups.size()
    elif agg == "Somme":
        values = groups[y].sum(min_count=1)
    else:
        values = groups[y].agg(AGGREGATIONS[agg])
    result = values.rename_axis("Groupe").rename("Valeur").reset_index()
    if kind != "Courbe":
        if spec["sort"] != "Groupe":
            result = result.sort_values("Valeur", ascending=spec["sort"] == "Valeur croissante", kind="stable")
        result = result.head(spec["limit"])
    return result, excluded
