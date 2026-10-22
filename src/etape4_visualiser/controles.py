"""Étape 4 (Visualiser) : graphiques de contrôle et phrases « À retenir ».

Entrées : données corrigées préparées (`prepare`) et rôles des colonnes.
Sorties : des graphiques décrits par leurs données et leurs textes ; le dessin est fait par l'écran.
Les phrases sont générées par des règles générales : elles décrivent ce que montrent les
données (valeur la plus fréquente, effectifs faibles, volume par période), jamais une
interprétation métier.
"""
import numpy as np
import pandas as pd

from src.config import (CATEGORIES_GRAPHIQUE, CATEGORIES_MAX_POUR_REPARTITION, LIBELLE_MANQUANT,
                        VALEURS_MIN_MOYENNE)
from src.core.dates import compter_par_periode
from src.core.statistiques import tukey_bounds
from src.core.texte import nombre_lisible


def repartition(data, col):
    """Nombre de lignes par valeur d'une colonne : les plus fréquentes, puis « Autres », puis les manquantes."""
    values = data[col].astype("string")
    counts = values.value_counts()
    top = counts.head(CATEGORIES_GRAPHIQUE)
    lignes = [{"Groupe": str(k), "Lignes": int(v), "Type": "valeur"} for k, v in top.items()]
    autres = int(counts.iloc[CATEGORIES_GRAPHIQUE:].sum())
    if autres:
        lignes.append({"Groupe": f"Autres ({len(counts) - CATEGORIES_GRAPHIQUE} valeurs)", "Lignes": autres, "Type": "autres"})
    manquantes = int(values.isna().sum())
    if manquantes:
        lignes.append({"Groupe": LIBELLE_MANQUANT, "Lignes": manquantes, "Type": "manquant"})
    retenir = []
    if len(top):
        retenir.append(f"« {top.index[0]} » est la valeur la plus fréquente : "
                       f"{nombre_lisible(int(top.iloc[0]))} lignes sur {nombre_lisible(len(data))}.")
    if manquantes:
        retenir.append(f"{nombre_lisible(manquantes)} lignes n'ont pas de valeur dans {col}.")
    return {"genre": "barres", "titre": f"Nombre de lignes par {col}", "sous_titre": f"{nombre_lisible(len(data))} lignes",
            "donnees": pd.DataFrame(lignes, columns=["Groupe", "Lignes", "Type"]), "a_retenir": retenir}


def distribution(data, col):
    """Histogramme d'une mesure, avec la médiane et les valeurs inhabituelles (Tukey), conservées."""
    values = data[col].dropna()
    if values.empty:
        return None
    vides = len(data) - len(values)
    classes = min(20, max(5, int(np.sqrt(len(values)))))
    effectifs, bornes = np.histogram(values, bins=classes)
    bas, haut = tukey_bounds(values)
    inhabituelles = int(((values < bas) | (values > haut)).sum())
    retenir = [f"La moitié des valeurs est inférieure à {nombre_lisible(float(values.median()))}."]
    if inhabituelles:
        retenir.append(f"{nombre_lisible(inhabituelles)} valeurs sortent nettement du lot : à vérifier, pas à supprimer automatiquement.")
    sous_titre = f"{nombre_lisible(len(values))} valeurs renseignées" + (f" · {nombre_lisible(vides)} cases vides ignorées" if vides else "")
    return {"genre": "histogramme", "titre": f"Répartition de {col}", "sous_titre": sous_titre,
            "donnees": pd.DataFrame({"Début": bornes[:-1], "Fin": bornes[1:], "Lignes": effectifs}), "a_retenir": retenir}


def comparaison(data, groupe, mesure):
    """Moyenne d'une mesure par groupe, avec le nombre de valeurs de chaque groupe (fragile si trop peu)."""
    valides = data[[groupe, mesure]].dropna(subset=[mesure])
    if valides.empty:
        return None
    vides = len(data) - len(valides)
    groupes = valides[groupe].astype("string").fillna(LIBELLE_MANQUANT)
    stats = valides[mesure].groupby(groupes).agg(["mean", "size"])
    # Les groupes les plus fournis d'abord, puis tri par moyenne pour la lecture.
    stats = stats.loc[stats["size"].sort_values(ascending=False, kind="stable").index[:CATEGORIES_GRAPHIQUE]]
    stats = stats.sort_values("mean", ascending=False, kind="stable")
    donnees = pd.DataFrame({"Groupe": stats.index.astype(str), "Moyenne": stats["mean"].to_numpy(),
                            "Valeurs": stats["size"].to_numpy().astype(int)})
    donnees["Fragile"] = donnees["Valeurs"] < VALEURS_MIN_MOYENNE
    fragiles = donnees.loc[donnees["Fragile"], "Groupe"].tolist()
    if fragiles:
        noms = ", ".join(f"« {g} »" for g in fragiles[:3]) + (" …" if len(fragiles) > 3 else "")
        retenir = [f"{noms} : moins de {VALEURS_MIN_MOYENNE} valeurs. Ces moyennes sont trop fragiles pour conclure."]
    else:
        haut, bas = donnees.iloc[0], donnees.iloc[-1]
        retenir = [f"Moyenne la plus haute : « {haut['Groupe']} » ({nombre_lisible(float(haut['Moyenne']))}), "
                   f"la plus basse : « {bas['Groupe']} » ({nombre_lisible(float(bas['Moyenne']))})."]
    retenir.append("Une moyenne résume un groupe ; elle ne dit pas pourquoi les groupes diffèrent.")
    sous_titre = f"{nombre_lisible(len(valides))} valeurs renseignées" + (f" · {nombre_lisible(vides)} cases vides ignorées" if vides else "")
    return {"genre": "moyennes", "titre": f"Moyenne de {mesure} par {groupe}", "sous_titre": sous_titre,
            "donnees": donnees, "a_retenir": retenir}


def evolution(data, col):
    """Nombre de lignes par période (jour, mois ou année selon l'étendue des dates)."""
    donnees, unite = compter_par_periode(data[col])
    if unite is None:
        return None
    illisibles = int(data[col].isna().sum())
    pic = donnees.loc[donnees["Lignes"].idxmax()]
    periode = str(pic["Période"])
    retenir = [f"{periode[:1].upper()}{periode[1:]} compte le plus de lignes ({nombre_lisible(int(pic['Lignes']))}).",
               "Un volume plus élevé n'indique pas une meilleure performance : c'est seulement un nombre de lignes."]
    if illisibles:
        retenir.append(f"{nombre_lisible(illisibles)} lignes sans date lisible ne sont pas comptées.")
    return {"genre": "periodes", "titre": f"Nombre de lignes par {unite}", "sous_titre": col,
            "donnees": donnees, "a_retenir": retenir}


def graphiques_controle(data, roles):
    """Jusqu'à trois graphiques choisis selon les rôles : répartition, comparaison (ou distribution), évolution."""
    def premiere(role, condition):
        return next((c for c, r in roles.items() if r == role and condition(c)), None)

    categorie = premiere("Catégorie", lambda c: 2 <= data[c].nunique() <= CATEGORIES_MAX_POUR_REPARTITION)
    mesure = premiere("Mesure", lambda c: data[c].notna().any())
    date = premiere("Date", lambda c: data[c].notna().any())
    graphiques = []
    if categorie:
        graphiques.append(repartition(data, categorie))
    if mesure:
        graphiques.append(comparaison(data, categorie, mesure) if categorie else distribution(data, mesure))
    if date:
        graphiques.append(evolution(data, date))
    return [g for g in graphiques if g is not None]
