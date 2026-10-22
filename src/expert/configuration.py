"""Mode expert : validation des configurations JSON du dashboard avant import."""


import numpy as np
import pandas as pd

from src.etape4_visualiser.graphiques import AGGREGATIONS, KINDS, PERIODS


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
