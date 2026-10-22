"""Suggestions, filtres et agrégations sans dépendance à l'interface."""
import itertools
import re
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype
from pandas.tseries.api import guess_datetime_format

from src.analysis import numeric_columns

KINDS = ["Histogramme", "Boîte à moustaches", "Barres", "Courbe", "Nuage de points", "Tableau croisé"]
AGGREGATIONS = {"Effectif": "size", "Somme": "sum", "Moyenne": "mean", "Médiane": "median"}
ROLES = ["Mesure", "Catégorie", "Date", "Identifiant"]
PERIODS = {"Jour": "D", "Mois": "MS", "Année": "YS"}
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


def validate_configuration(config, roles):
    """Refuse les configurations incompatibles avant de modifier la session."""
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Version de configuration non reconnue.")
    if config.get("roles") != roles:
        raise ValueError("Les colonnes et leurs rôles doivent correspondre à la configuration.")
    if not isinstance(config.get("charts"), list) or len(config["charts"]) > 30:
        raise ValueError("La configuration doit contenir au maximum 30 graphiques.")

    def filters(items):
        if not isinstance(items, list) or len(items) > len(roles):
            raise ValueError("Filtres invalides.")
        for f in items:
            col = f["column"]
            expected = roles.get(col)
            expected = "Catégorie" if expected in ("Catégorie", "Identifiant") else expected
            if f["type"] != expected or not isinstance(f["missing"], bool):
                raise ValueError("Type de filtre incompatible.")
            if expected == "Catégorie":
                if not isinstance(f["values"], list) or not all(isinstance(v, str) for v in f["values"]):
                    raise ValueError("Valeurs catégorielles invalides.")
                if not isinstance(f.get("exclude", False), bool):
                    raise ValueError("Mode de filtre invalide.")
            elif expected == "Date":
                low, high = pd.Timestamp(f["low"]), pd.Timestamp(f["high"])
                if pd.isna(low) or pd.isna(high) or low.tzinfo or high.tzinfo or low != low.normalize() or high != high.normalize() or low > high:
                    raise ValueError("Intervalle de dates invalide.")
            elif expected == "Mesure":
                if not all(isinstance(f[k], (float, int)) and np.isfinite(f[k]) for k in ("low", "high")) or f["low"] > f["high"]:
                    raise ValueError("Intervalle numérique invalide.")
            else:
                raise ValueError("Colonne de filtre absente.")

    filters(config.get("filters"))
    for c in config["charts"]:
        kind, x, y = c["kind"], c["x"], c["y"]
        if kind not in KINDS or x not in roles or c["agg"] not in AGGREGATIONS:
            raise ValueError("Graphique invalide.")
        if kind in ("Histogramme", "Boîte à moustaches", "Nuage de points") and roles[x] != "Mesure":
            raise ValueError("Une mesure est requise.")
        if kind == "Courbe" and roles[x] != "Date":
            raise ValueError("Une date est requise.")
        if kind in ("Barres", "Tableau croisé") and roles[x] != "Catégorie":
            raise ValueError("Une catégorie est requise.")
        if kind == "Nuage de points" and (roles.get(y) != "Mesure" or x == y):
            raise ValueError("Deux mesures distinctes sont requises.")
        if kind == "Tableau croisé" and (roles.get(y) != "Catégorie" or x == y):
            raise ValueError("Deux catégories distinctes sont requises.")
        if kind in ("Barres", "Courbe") and c["agg"] != "Effectif" and roles.get(y) != "Mesure":
            raise ValueError("La mesure d'agrégation est absente.")
        if c["period"] not in PERIODS or c["sort"] not in ("Groupe", "Valeur croissante", "Valeur décroissante"):
            raise ValueError("Options de tri ou de période invalides.")
        # « row » n'existe que dans les configurations antérieures : accepté pour l'import.
        if ("row" in c and (type(c["row"]) is not int or not 1 <= c["row"] <= 30)) or c["width"] not in ("Demi", "Pleine"):
            raise ValueError("Disposition invalide.")
        if type(c["limit"]) is not int or not 1 <= c["limit"] <= 100 or not isinstance(c["title"], str) or len(c["title"]) > 200:
            raise ValueError("Titre ou limite invalide.")
        filters(c["filters"])
    return config
