"""Étape 5 : résumé de chaque analyse affichée, au format des graphiques du rapport.

Entrées : résultats de `calculs` et réglages choisis à l'écran. Sortie : un dictionnaire par analyse
{genre, titre, sous_titre, donnees, titre_valeur | titre_y, a_retenir, prudence, tableau} que le rapport
complet affiche tel quel (graphique dessiné, tableau des premiers groupes, constats).
"""
import pandas as pd

from src.config import CATEGORIES_GRAPHIQUE
from src.core.texte import nombre_lisible
from src.etape2_comprendre.repetitions import part_lisible
from src.etape5_analyser.calculs import STATISTIQUES, de, duree_lisible

PRUDENCE_COMPARER = "Une comparaison montre une différence, pas sa cause."
PRUDENCE_DELAI = "L'outil ne dit pas « en retard » : il ne connaît pas vos objectifs de délai."
PRUDENCE_EVOLUTION = "Un volume plus élevé n'indique pas une meilleure ou une moins bonne performance."


def prudence_delai(unite):
    return PRUDENCE_DELAI + (" Le délai est calculé une fois par élément (sa dernière ligne)." if unite != "lignes" else "")


def _valeur(valeur, statistique):
    return nombre_lisible(int(valeur)) if statistique == "nombre" else nombre_lisible(round(float(valeur), 2))


def resume_comparaison(resultat, groupe, statistique, mesure, unite):
    ce_qu_on_compte = f"nombre {de(unite)}" if statistique == "nombre" else f"{STATISTIQUES[statistique].lower()} de {mesure}"
    haut = resultat["tableau"].head(CATEGORIES_GRAPHIQUE)
    colonnes = {groupe: haut["Groupe"], STATISTIQUES[statistique]: [_valeur(v, statistique) for v in haut["Valeur"]]}
    if statistique != "nombre":
        # Pour un comptage, l'effectif est la valeur elle-même.
        colonnes["Effectif"] = [nombre_lisible(int(n)) for n in haut["Effectif"]]
    colonnes["Part"] = [part_lisible(p) for p in haut["Effectif"] / resultat["tableau"]["Effectif"].sum()]
    return {"genre": "classement", "titre": f"Comparer des groupes : {groupe}", "sous_titre": f"{groupe} · {ce_qu_on_compte}",
            "donnees": resultat["graphique"],
            "titre_valeur": "Nombre" if statistique == "nombre" else STATISTIQUES[statistique],
            "a_retenir": resultat["constats"], "prudence": PRUDENCE_COMPARER,
            "tableau": pd.DataFrame(colonnes)}


def resume_delai(resultat, debut, fin, groupe, unite_temps, unite):
    mediane = duree_lisible(resultat["mediane"], unite_temps) if resultat["mediane"] is not None else "—"
    tableau = None
    if resultat["tableau"] is not None:
        haut = resultat["tableau"].head(CATEGORIES_GRAPHIQUE)
        tableau = pd.DataFrame({groupe: haut["Groupe"],
                                "Délai médian": [duree_lisible(v, unite_temps) for v in haut["Valeur"]],
                                "Effectif": [nombre_lisible(int(n)) for n in haut["Effectif"]]})
    return {"genre": "classement", "titre": f"Mesurer un délai : {debut} → {fin}",
            "sous_titre": (f"{'par ' + groupe + ' · ' if groupe else ''}délai médian, tous : {mediane} · "
                           f"{nombre_lisible(resultat['calculables'])} / {nombre_lisible(resultat['total'])} délais calculables"),
            "donnees": resultat["graphique"], "titre_valeur": "Délai médian", "a_retenir": resultat["constats"],
            "prudence": prudence_delai(unite), "tableau": tableau}


def resume_evolution(resultat, date, groupe, valeur, unite):
    pour = f" · pour {groupe} = « {valeur} »" if groupe and valeur is not None else ""
    return {"genre": "periodes", "titre": f"Évolution dans le temps : {date}",
            "sous_titre": f"nombre {de(unite)} par {resultat['unite']}{pour}", "donnees": resultat["donnees"],
            "titre_y": unite.capitalize(), "a_retenir": resultat["constats"], "prudence": PRUDENCE_EVOLUTION, "tableau": None}
