"""Lecture des dates et découpage en périodes, communs aux étapes 2 (résumé) et 4 (graphiques).

Entrée : une colonne brute (texte, nombre ou date). Sortie : des dates sans fuseau (UTC),
NaT pour les valeurs illisibles. Un seul format est appliqué à toute la colonne.
"""
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype
from pandas.tseries.api import guess_datetime_format

MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
# Fréquences pandas des périodes affichées.
FREQUENCES = {"jour": "D", "mois": "MS", "année": "YS"}


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


def unite_periode(debut, fin):
    """Unité lisible pour un intervalle : jour (≤ 2 mois), mois (≤ 3 ans), sinon année."""
    jours = (fin - debut).days
    if jours <= 62:
        return "jour"
    return "mois" if jours <= 3 * 366 else "année"


def libelle_periode(moment, unite, plusieurs_annees=True):
    """« 5 mars », « mars 2026 » (ou « mars » sur une seule année), « 2026 »."""
    if unite == "année":
        return str(moment.year)
    mois = MOIS_COURTS[moment.month - 1]
    if unite == "jour":
        return f"{moment.day} {mois}"
    return f"{mois} {moment.year}" if plusieurs_annees else mois


def compter_par_periode(dates):
    """Nombre de dates par période, périodes sans ligne incluses (0 : aucune ligne, ce n'est pas une absence de donnée)."""
    valides = dates.dropna()
    if valides.empty:
        return pd.DataFrame(columns=["Période", "Lignes"]), None
    unite = unite_periode(valides.min(), valides.max())
    comptes = valides.to_frame("d").set_index("d").resample(FREQUENCES[unite]).size()
    plusieurs = valides.dt.year.nunique() > 1
    return pd.DataFrame({"Période": [libelle_periode(m, unite, plusieurs) for m in comptes.index],
                         "Lignes": comptes.to_numpy()}), unite
