"""Étape 5 : continuer l'analyse ailleurs — export CSV (Power BI, Excel…) et notebook Jupyter.

Entrées : données préparées (types de l'étape Comprendre), types des colonnes et réglages choisis
à l'écran. Sorties : un ZIP (données corrigées, dictionnaire, mode d'emploi) et un notebook seul, qui
lit le CSV de ce ZIP (pas de copie des données). Le notebook est écrit à partir d'un modèle (pas d'IA) ;
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


def export_csv(data, roles, delai=None):
    """ZIP : données corrigées (avec la colonne de délai si elle est calculée), dictionnaire, mode d'emploi."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(FICHIER_DONNEES, csv_bytes(_avec_delai(data, delai)))
        archive.writestr("dictionnaire_colonnes.csv", csv_bytes(dictionnaire_colonnes(data, roles, delai)))
        archive.writestr("LISEZMOI.txt",
                         "Commencez par extraire ce ZIP : clic droit > Extraire tout. Un fichier ouvert directement dans "
                         "le ZIP n'est pas utilisable.\n\n"
                         "donnees_corrigees.csv : les données après vos corrections (UTF-8, séparateur virgule).\n"
                         "dictionnaire_colonnes.csv : le type et le format de chaque colonne.\n\n"
                         "Power BI Desktop : Accueil > Obtenir les données > Texte/CSV > donnees_corrigees.csv ; "
                         "vérifiez les types dans Power Query avec le dictionnaire (les identifiants restent du texte).\n"
                         "Excel : Données > À partir d'un fichier texte/CSV (Excel s'arrête à 1 048 576 lignes).\n"
                         "Jupyter : placez le notebook téléchargé à l'étape Analyser dans ce dossier.\n\n"
                         "Une case vide est une valeur manquante, pas un zéro.\n")
    return tampon.getvalue()


def _md(*lignes):
    return {"cell_type": "markdown", "metadata": {}, "source": "\n".join(lignes)}


def _code(*lignes, graphique=False):
    # Étiquette « graphique » : cellules qui demandent matplotlib.
    return {"cell_type": "code", "execution_count": None, "metadata": {"tags": ["graphique"]} if graphique else {},
            "outputs": [], "source": "\n".join(lignes)}


def _par_type(roles, *types):
    return [c for c, role in roles.items() if role in types]


def _decouverte(nom_fichier, roles):
    """Les étapes d'une analyse : charger, voir, contrôler la qualité, résumer, regarder en graphiques."""
    identifiants, categories = _par_type(roles, "Identifiant"), _par_type(roles, "Catégorie")
    nombres, dates = _par_type(roles, "Mesure"), _par_type(roles, "Date")
    cellules = [
        _md(f"# Analyse de {nom_fichier}",
            "Notebook généré par l'outil « Analyse simple » à partir des données corrigées.",
            "",
            "**Avant de commencer** : extrayez l'export CSV (clic droit > Extraire tout) et placez ce notebook dans le "
            "même dossier que `donnees_corrigees.csv`."),
        _md("## 1. Charger les données",
            "Les identifiants et les catégories sont lus comme du texte (les zéros au début sont gardés), les dates comme des dates."),
        _code("import pandas as pd", "",
              f"FICHIER = {FICHIER_DONNEES!r}",
              f"IDENTIFIANTS = {identifiants!r}",
              f"CATEGORIES = {categories!r}",
              f"NOMBRES = {nombres!r}",
              f"DATES = {dates!r}",
              "donnees = pd.read_csv(FICHIER, dtype={c: 'string' for c in IDENTIFIANTS + CATEGORIES}, parse_dates=DATES)"),
        _md("## 2. Aperçu", "Combien de lignes et de colonnes, à quoi ressemblent les premières lignes, quel type a chaque colonne."),
        _code("print(f'{len(donnees):,} lignes et {donnees.shape[1]} colonnes'.replace(',', ' '))", "donnees.head(10)"),
        _code("donnees.dtypes.rename('type').to_frame()"),
        _md("## 3. Qualité", "Cases vides par colonne et lignes en double. Une case vide est une valeur manquante, pas un zéro."),
        _code("vides = donnees.isna().sum()",
              "qualite = pd.DataFrame({'cases vides': vides, '% vides': (100 * vides / len(donnees)).round(1),",
              "                        'valeurs différentes': donnees.nunique()})",
              "print('Lignes en double :', int(donnees.duplicated().sum()))",
              "qualite.sort_values('% vides', ascending=False)"),
    ]
    if nombres or categories:
        cellules.append(_md("## 4. Statistiques",
                            "Pour les nombres : moyenne, médiane, minimum, maximum, écart-type. Une moyenne loin de la "
                            "médiane signale quelques valeurs très grandes ou très petites. Pour les catégories : les "
                            "valeurs les plus fréquentes."))
    if nombres:
        cellules.append(_code("donnees[NOMBRES].agg(['count', 'mean', 'median', 'min', 'max', 'std']).T.round(2)"))
    if categories:
        cellules.append(_code("for colonne in CATEGORIES[:5]:",
                              "    print(colonne)",
                              "    print(donnees[colonne].value_counts(dropna=False).head(5).to_string(), '\\n')"))
    graphiques = []
    if nombres:
        graphiques.append(_code("COLONNE = NOMBRES[0]  # changez la colonne si besoin",
                                "donnees[COLONNE].plot.hist(bins=30, title=f'Répartition de {COLONNE}')",
                                "plt.show()", graphique=True))
    if categories:
        graphiques.append(_code("COLONNE = CATEGORIES[0]  # changez la colonne si besoin",
                                "donnees[COLONNE].fillna('Non renseignée').value_counts().head(10).sort_values()"
                                ".plot.barh(title=f'Nombre de lignes par {COLONNE}')",
                                "plt.show()", graphique=True))
    if dates:
        graphiques.append(_code("COLONNE = DATES[0]  # changez la colonne si besoin",
                                "donnees.dropna(subset=[COLONNE]).set_index(COLONNE).resample('MS').size()"
                                ".plot(title=f'Nombre de lignes par mois ({COLONNE})')",
                                "plt.show()", graphique=True))
    if graphiques:
        cellules += [_md("## 5. Graphiques", "Il faut matplotlib (présent dans les installations habituelles de Jupyter)."),
                     _code("import matplotlib.pyplot as plt", graphique=True)] + graphiques
    return cellules


def _analyses(reglages):
    """Les analyses choisies à l'étape Analyser."""
    r = reglages
    cellules = [_md("## 6. Analyses de l'étape Analyser")]
    if r.get("identifiant"):
        cellules += [_md(f"Chaque valeur de `{r['identifiant']}` n'est comptée qu'une fois (sa dernière ligne)."),
                     _code(f"IDENTIFIANT = {r['identifiant']!r}",
                           "unites = donnees.dropna(subset=[IDENTIFIANT]).drop_duplicates(IDENTIFIANT, keep='last')",
                           "len(unites)")]
    else:
        cellules.append(_code("unites = donnees"))
    if r.get("groupe"):
        cellules += [_md("### Comparer des groupes",
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
        cellules += [_md("### Mesurer un délai", "Une date de fin avant la date de début est ignorée."), _code(*lignes)]
    if r.get("date"):
        cellules += [_md("### Évolution par mois"),
                     _code(f"DATE = {r['date']!r}",
                           "unites.dropna(subset=[DATE]).set_index(DATE).resample('MS').size()")]
    return cellules


def notebook(nom_fichier, roles, reglages):
    """Notebook Jupyter (format nbformat 4) : découverte des données, puis les analyses choisies.

    `reglages` : identifiant, groupe, statistique, mesure, debut, fin, unite_temps, date (chacun peut valoir None).
    """
    cellules = _decouverte(nom_fichier, roles) + _analyses(reglages)
    cellules.append(_md("## Pour aller plus loin",
                        "- Graphiques plus riches : `import seaborn as sns`, par exemple `sns.boxplot(data=unites, x=..., y=...)`.",
                        "- Une différence entre groupes ne dit pas sa cause : vérifiez-la avec ce que vous savez du métier."))
    return {"cells": cellules, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                            "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def notebook_ipynb(nom_fichier, roles, reglages):
    """Le notebook seul, en octets : il lit le CSV de l'export CSV, placé dans le même dossier."""
    return json.dumps(notebook(nom_fichier, roles, reglages), ensure_ascii=False, indent=1).encode("utf-8")
