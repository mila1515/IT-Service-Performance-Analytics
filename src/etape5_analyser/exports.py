"""Étape 5 : passerelles vers Power BI et Jupyter, pour continuer l'analyse métier ailleurs.

Entrées : données préparées (types de l'étape Comprendre), types des colonnes et réglages choisis
à l'écran. Sorties : deux archives ZIP. Le notebook est écrit à partir d'un modèle (pas d'IA) ;
les noms de colonnes y sont des chaînes Python (`repr`), jamais du code.
"""
import io
import json
import zipfile

import pandas as pd

from src.config import GROUPE_MIN_COMPARAISON, LIBELLE_MANQUANT
from src.etape2_comprendre.colonnes import LIBELLES_ROLES
from src.etape4_visualiser.export import csv_bytes

FICHIER_DONNEES = "donnees_corrigees.csv"
FORMATS = {"Identifiant": "texte (les zéros au début sont gardés)", "Catégorie": "texte",
           "Mesure": "nombre décimal, point comme séparateur", "Date": "date et heure, format ISO (AAAA-MM-JJ HH:MM:SS)"}


def nom_colonne_delai(debut, fin, unite_temps):
    return f"delai_{unite_temps}_{debut}_{fin}"


def dictionnaire_colonnes(data, roles, delai=None):
    """Une ligne par colonne : type, format dans le fichier, part remplie."""
    lignes = [{"Colonne": c, "Type": LIBELLES_ROLES[roles[c]], "Format dans le fichier": FORMATS[roles[c]],
               "Remplie (%)": round(100 * data[c].notna().mean(), 1) if len(data) else 0,
               "Case vide": "valeur manquante (pas un zéro)"} for c in data.columns if c in roles]
    if delai is not None:
        nom, valeurs = delai
        lignes.append({"Colonne": nom, "Type": "Nombre", "Format dans le fichier": "nombre décimal (calculé : fin − début)",
                       "Remplie (%)": round(100 * valeurs.notna().mean(), 1) if len(valeurs) else 0,
                       "Case vide": "date de début ou de fin manquante"})
    return pd.DataFrame(lignes)


def _avec_delai(data, delai):
    return data if delai is None else data.assign(**{delai[0]: delai[1].round(4)})


def export_power_bi(data, roles, delai=None):
    """ZIP : données corrigées (avec la colonne de délai si elle est calculée), dictionnaire, mode d'emploi."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FICHIER_DONNEES, csv_bytes(_avec_delai(data, delai)))
        archive.writestr("dictionnaire_colonnes.csv", csv_bytes(dictionnaire_colonnes(data, roles, delai)))
        archive.writestr("LISEZMOI.txt",
                         "Import dans Power BI Desktop : Accueil > Obtenir les données > Texte/CSV > donnees_corrigees.csv.\n"
                         "Origine du fichier : 65001 (UTF-8). Délimiteur : virgule.\n"
                         "Vérifiez les types dans l'éditeur Power Query avec dictionnaire_colonnes.csv "
                         "(les identifiants restent du texte).\n"
                         "Une case vide est une valeur manquante, pas un zéro.\n")
    return tampon.getvalue()


def _md(*lignes):
    return {"cell_type": "markdown", "metadata": {}, "source": "\n".join(lignes)}


def _code(*lignes):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": "\n".join(lignes)}


def notebook(nom_fichier, roles, reglages):
    """Notebook Jupyter (format nbformat 4) qui recharge les données et refait les analyses choisies.

    `reglages` : identifiant, groupe, statistique, mesure, debut, fin, unite_temps, date (chacun peut valoir None).
    """
    r = reglages
    textes = [c for c, role in roles.items() if role in ("Identifiant", "Catégorie")]
    dates = [c for c, role in roles.items() if role == "Date"]
    cellules = [
        _md(f"# Analyse de {nom_fichier}",
            "Notebook généré par l'outil « Analyse simple » à partir des données corrigées.",
            "Il refait les analyses de l'étape Analyser ; complétez-le avec vos propres questions."),
        _code("import pandas as pd", "",
              f"FICHIER = {FICHIER_DONNEES!r}",
              f"TEXTES = {textes!r}  # identifiants et catégories : lus comme du texte",
              f"DATES = {dates!r}",
              "donnees = pd.read_csv(FICHIER, dtype={c: 'string' for c in TEXTES}, parse_dates=DATES)",
              "donnees.head()"),
    ]
    if r.get("identifiant"):
        cellules += [_md("## Une ligne par identifiant",
                         f"Chaque valeur de `{r['identifiant']}` n'est comptée qu'une fois (sa dernière ligne)."),
                     _code(f"IDENTIFIANT = {r['identifiant']!r}",
                           "unites = donnees.dropna(subset=[IDENTIFIANT]).drop_duplicates(IDENTIFIANT, keep='last')",
                           "len(unites)")]
    else:
        cellules.append(_code("unites = donnees"))
    if r.get("groupe"):
        cellules += [_md("## Comparer des groupes",
                         f"Les groupes de moins de {GROUPE_MIN_COMPARAISON} éléments sont trop petits pour conclure.")]
        lignes = [f"GROUPE = {r['groupe']!r}", f"groupes = unites[GROUPE].fillna({LIBELLE_MANQUANT!r})"]
        if r.get("statistique") in ("moyenne", "mediane") and r.get("mesure"):
            fonction = "mean" if r["statistique"] == "moyenne" else "median"
            lignes += [f"MESURE = {r['mesure']!r}",
                       f"comparaison = unites[MESURE].groupby(groupes).agg(['{fonction}', 'count'])",
                       f"comparaison.sort_values('{fonction}', ascending=False)"]
        else:
            lignes += ["comparaison = groupes.value_counts().to_frame('nombre')",
                       "comparaison.assign(part=comparaison['nombre'] / comparaison['nombre'].sum())"]
        cellules.append(_code(*lignes))
    if r.get("debut") and r.get("fin"):
        secondes = 86400 if r.get("unite_temps", "jours") == "jours" else 3600
        lignes = [f"DEBUT, FIN = {r['debut']!r}, {r['fin']!r}",
                  f"delai = (unites[FIN] - unites[DEBUT]).dt.total_seconds() / {secondes}  # en {r.get('unite_temps', 'jours')}",
                  "unites = unites.assign(delai=delai.where(delai >= 0))",
                  "print('Délai médian :', unites['delai'].median())"]
        if r.get("groupe"):
            lignes += ["delais = unites.groupby(unites[GROUPE].fillna(" + repr(LIBELLE_MANQUANT) + "))['delai'].agg(['median', 'count'])",
                       f"delais[delais['count'] >= {GROUPE_MIN_COMPARAISON}].sort_values('median', ascending=False)"]
        cellules += [_md("## Mesurer un délai", "Une date de fin avant la date de début est ignorée."), _code(*lignes)]
    if r.get("date"):
        cellules += [_md("## Évolution par mois"),
                     _code(f"DATE = {r['date']!r}",
                           "unites.dropna(subset=[DATE]).set_index(DATE).resample('MS').size()")]
    cellules.append(_md("## Pour aller plus loin",
                        "- Graphiques : `import seaborn as sns` puis, par exemple, `sns.boxplot(data=unites, x='delai', y=GROUPE)`.",
                        "- Une différence entre groupes ne dit pas sa cause : vérifiez-la avec ce que vous savez du métier."))
    return {"cells": cellules, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                            "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def export_jupyter(data, roles, nom_fichier, reglages):
    """ZIP : le notebook et les données corrigées qu'il recharge."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("analyse.ipynb", json.dumps(notebook(nom_fichier, roles, reglages), ensure_ascii=False, indent=1))
        archive.writestr(FICHIER_DONNEES, csv_bytes(data))
        archive.writestr("LISEZMOI.txt", "Ouvrez analyse.ipynb dans Jupyter (ou VS Code) dans ce dossier, puis exécutez les cellules.\n"
                                         "Le notebook recharge donnees_corrigees.csv, placé à côté.\n")
    return tampon.getvalue()
