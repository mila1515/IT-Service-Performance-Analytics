"""Dessin des graphiques (Altair) à partir des descriptions produites par `etape4_visualiser.controles`.

Utilisé par l'étape 2 (mini-graphiques des colonnes) et l'étape 4 (graphiques de contrôle).
Règles : une seule couleur pour les valeurs, un gris pour « non renseignée », la même couleur
plus claire pour une moyenne fragile ; chaque barre porte sa valeur écrite, pour ne jamais distinguer par la
couleur seule. Couleurs validées (contraste et daltonisme) ; fond transparent, pour s'afficher sur les cartes blanches.
"""
import altair as alt
import pandas as pd

from src.config import COULEUR_FRAGILE, COULEUR_MANQUANT, COULEUR_PRINCIPALE
from src.core.texte import nombre_lisible

ENCRE = "#1E2A38"
GRILLE = "#E1E6EA"
FOND = "transparent"
# Au-delà, les étiquettes au-dessus des colonnes se chevaucheraient.
PERIODES_ETIQUETEES = 12
PERIODES_EN_COLONNES = 36


def _barres_horizontales(donnees, valeur, etiquette, couleur, titre_valeur):
    hauteur = max(60, 34 * len(donnees))
    base = alt.Chart(donnees).encode(
        y=alt.Y("Groupe:N", sort=None, title=None, axis=alt.Axis(labelLimit=200, ticks=False, domain=False, labelPadding=8)),
        x=alt.X(f"{valeur}:Q", title=None, axis=None, scale=alt.Scale(domainMin=0)))
    barres = base.mark_bar(size=18, cornerRadiusEnd=4).encode(
        color=alt.Color(f"{couleur}:N", scale=None, legend=None),
        tooltip=[alt.Tooltip("Groupe:N", title="Groupe"), alt.Tooltip(f"{etiquette}:N", title=titre_valeur)])
    textes = base.mark_text(align="left", dx=6, color=ENCRE, fontSize=13).encode(text=f"{etiquette}:N")
    return (barres + textes).properties(height=hauteur, background=FOND)


def repartition(donnees):
    """Barres horizontales « nombre de lignes par valeur », la valeur manquante en gris."""
    donnees = donnees.assign(
        Etiquette=[nombre_lisible(int(v)) for v in donnees["Lignes"]],
        Couleur=[COULEUR_MANQUANT if t == "manquant" else COULEUR_PRINCIPALE for t in donnees["Type"]])
    return _barres_horizontales(donnees, "Lignes", "Etiquette", "Couleur", "Lignes")


def moyennes(donnees):
    """Moyenne par groupe ; une moyenne calculée sur trop peu de valeurs est plus claire et le dit."""
    donnees = donnees.assign(
        Etiquette=[f"{nombre_lisible(float(m))} · {nombre_lisible(int(n))} val." for m, n in zip(donnees["Moyenne"], donnees["Valeurs"])],
        Couleur=[COULEUR_FRAGILE if f else COULEUR_PRINCIPALE for f in donnees["Fragile"]])
    return _barres_horizontales(donnees, "Moyenne", "Etiquette", "Couleur", "Moyenne")


def histogramme(donnees, titre_x):
    """Répartition d'une mesure par classes de valeurs."""
    return alt.Chart(donnees).mark_bar(color=COULEUR_PRINCIPALE, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("Début:Q", title=titre_x, bin="binned", axis=alt.Axis(grid=False, domainColor=GRILLE, tickColor=GRILLE)),
        x2="Fin:Q",
        y=alt.Y("Lignes:Q", title="Lignes", axis=alt.Axis(format="d", tickMinStep=1, gridColor=GRILLE, domain=False, ticks=False)),
        tooltip=[alt.Tooltip("Début:Q", title="De", format=",.2f"), alt.Tooltip("Fin:Q", title="À", format=",.2f"),
                 alt.Tooltip("Lignes:Q", title="Lignes")],
    ).properties(height=220, background=FOND)


def periodes(donnees):
    """Nombre de lignes par période ; colonnes jusqu'à 36 périodes, courbe au-delà."""
    donnees = donnees.assign(Etiquette=[nombre_lisible(int(v)) for v in donnees["Lignes"]])
    x = alt.X("Période:N", sort=None, title=None, axis=alt.Axis(labelAngle=0 if len(donnees) <= PERIODES_ETIQUETEES else -45,
                                                                 ticks=False, domainColor=GRILLE))
    y = alt.Y("Lignes:Q", title="Lignes", axis=alt.Axis(format="d", tickMinStep=1, gridColor=GRILLE, domain=False, ticks=False))
    tooltip = [alt.Tooltip("Période:N"), alt.Tooltip("Etiquette:N", title="Lignes")]
    base = alt.Chart(donnees).encode(x=x, y=y, tooltip=tooltip)
    if len(donnees) > PERIODES_EN_COLONNES:
        return base.mark_line(color=COULEUR_PRINCIPALE, strokeWidth=2).properties(height=240, background=FOND)
    graphique = base.mark_bar(color=COULEUR_PRINCIPALE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    if len(donnees) <= PERIODES_ETIQUETEES:
        graphique += base.mark_text(dy=-8, color=ENCRE, fontSize=13).encode(text="Etiquette:N")
    return graphique.properties(height=240, background=FOND)


def dessiner(graphique):
    """Graphique Altair correspondant à une description de `controles` (clé « genre »)."""
    donnees = graphique["donnees"]
    if graphique["genre"] == "barres":
        return repartition(donnees)
    if graphique["genre"] == "moyennes":
        return moyennes(donnees)
    if graphique["genre"] == "histogramme":
        return histogramme(donnees, graphique["titre"].removeprefix("Répartition de "))
    return periodes(donnees)


def mini_repartition(frequences):
    """Petit graphique d'une carte de colonne : [(valeur, effectif), …]."""
    return repartition(pd.DataFrame({"Groupe": [v for v, _ in frequences], "Lignes": [n for _, n in frequences],
                                     "Type": ["valeur"] * len(frequences)}))
