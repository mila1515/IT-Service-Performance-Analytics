"""Lecture d'un fichier CSV importé (étape 1), commune au parcours simple.

Entrée : le contenu du fichier (octets) et les options de lecture. Sortie : un tableau pandas
où seules les cellules vides sont manquantes (« NA », « ? »… restent des valeurs).
Les colonnes proposées comme identifiants sont relues en texte pour garder leurs zéros
initiaux (001 reste 001). Le fichier d'origine n'est jamais modifié.
"""
import io

import pandas as pd

from src.core.roles import infer_roles
from src.core.statistiques import numeric_columns

SEPARATEURS = {",": "Virgule ( , )", ";": "Point-virgule ( ; )", "\t": "Tabulation", "|": "Barre ( | )"}
ENCODAGES = {"utf-8-sig": "UTF-8 (le plus courant)", "cp1252": "Windows (Excel ancien)"}
DECIMALES = {".": "Point ( 10.5 )", ",": "Virgule ( 10,5 )"}


def lire_csv(contenu, separateur=",", encodage="utf-8-sig", decimale=".", colonnes_texte=()):
    """Lit le CSV ; seules les cellules vides deviennent des valeurs manquantes."""
    return pd.read_csv(io.BytesIO(contenu), sep=separateur, encoding=encodage, decimal=decimale,
                       dtype={c: "string" for c in colonnes_texte}, keep_default_na=False, na_values=[""])


def lire_avec_identifiants(contenu, separateur=",", encodage="utf-8-sig", decimale="."):
    """Lit le CSV puis relit en texte les identifiants lus comme nombres. Retourne (données, colonnes relues)."""
    data = lire_csv(contenu, separateur, encodage, decimale)
    identifiants = [c for c, role in infer_roles(data).items() if role == "Identifiant" and c in numeric_columns(data)]
    if identifiants:
        data = lire_csv(contenu, separateur, encodage, decimale, tuple(identifiants))
    return data, identifiants


def separateur_probablement_faux(data):
    """Vrai si tout le fichier tient dans une seule colonne dont le nom contient un autre séparateur."""
    if len(data.columns) != 1:
        return False
    return any(sep in str(data.columns[0]) for sep in SEPARATEURS)
