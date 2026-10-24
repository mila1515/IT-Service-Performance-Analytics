"""Graphiques Altair partagés par l'écran (app.py) et le rapport Word (rapport.py).

Une seule définition par graphique : le rapport imprime exactement ce que l'écran affiche.
"""
import altair as alt
import vl_convert

from indicateurs import (effet_reassignation, repartition, sla_par_equipe, sla_par_mois, sla_par_priorite,
                         tranches_delai, volume_par_mois)

# Couleurs du thème (.streamlit/config.toml).
BLEU, TURQUOISE, GRIS = "#1E40AF", "#0F766E", "#94A3B8"


def barres(data, x, y, titre_x, titre_y, horizontal=False, tri=None, domaine=None, infobulles=None,
           hauteur=260, gris=(), couleurs=None, angle=None):
    """Diagramme en barres d'une seule série (x = valeur, y = catégorie), avec infobulle.

    gris : catégories hors métier (« Inconnu », « Autres ») affichées en gris ;
    couleurs : {catégorie: couleur} quand chaque barre a sa propre identité.
    """
    echelle = alt.Scale(domain=domaine) if domaine else alt.Undefined
    # Graduations au format français : 24 918 (espace fine insécable comme séparateur de milliers).
    graduations = alt.Axis(labelExpr="replace(format(datum.value, ',d'), ',', ' ')")
    valeur = (alt.X if horizontal else alt.Y)(f"{x}:Q", title=titre_x, scale=echelle, axis=graduations)
    # Toutes les étiquettes de catégorie restent visibles et ne sont pas tronquées.
    axe = alt.Axis(labelOverlap=False, labelLimit=240, **({"labelAngle": angle} if angle is not None else {}))
    categorie = (alt.Y if horizontal else alt.X)(f"{y}:N", title=titre_y, sort=tri, axis=axe)
    if couleurs:
        couleur = alt.Color(f"{y}:N", scale=alt.Scale(domain=list(couleurs), range=list(couleurs.values())),
                            legend=None)
    elif gris:
        couleur = alt.condition(alt.FieldOneOfPredicate(field=y, oneOf=list(gris)), alt.value(GRIS), alt.value(BLEU))
    else:
        couleur = alt.value(BLEU)
    infobulles = infobulles or [alt.Tooltip(y, title=titre_y), alt.Tooltip(x, title=titre_x)]
    return (alt.Chart(data, height=hauteur, background="transparent").mark_bar(cornerRadiusEnd=4)
            .encode(categorie, valeur, color=couleur, tooltip=infobulles))


def infobulles_resume(nom, titre):
    """Infobulle commune aux tableaux de resume() : incidents, SLA et délais."""
    return [alt.Tooltip(nom, title=titre), alt.Tooltip("incidents", title="Incidents"),
            alt.Tooltip("sla_pct", title="SLA (%)"), alt.Tooltip("resolution_moyenne_h", title="Délai moyen (h)"),
            alt.Tooltip("resolution_mediane_h", title="Délai médian (h)")]


def hors_metier(valeurs):
    """Valeurs de remplacement à griser : « Inconnu » (non renseigné) et « Autres (n) »."""
    return [v for v in valeurs if v == "Inconnu" or str(v).startswith("Autres")]


# --- Un graphique par analyse (None si les données ne le permettent pas) ---------------------

def graphique_volume(df):
    return barres(volume_par_mois(df), "incidents", "mois", "Incidents", "Mois d'ouverture", angle=-45)


def graphique_sla_mois(df):
    return barres(sla_par_mois(df), "sla_pct", "mois", "Respect des SLA (%)", "Mois d'ouverture",
                  domaine=[0, 100], angle=-45, infobulles=infobulles_resume("mois", "Mois"))


def graphique_sla_priorite(df):
    priorites = sla_par_priorite(df)
    if priorites.empty:
        return None
    return barres(priorites, "sla_pct", "priority", "Respect des SLA (%)", "Priorité", horizontal=True,
                  tri="ascending", domaine=[0, 100], hauteur=200, gris=hors_metier(priorites["priority"]),
                  infobulles=infobulles_resume("priority", "Priorité"))


def graphique_reassignation(df):
    effet = effet_reassignation(df)
    if effet.empty:
        return None
    return barres(effet, "resolution_moyenne_h", "reassignment_status", "Délai moyen de résolution (h)", "",
                  horizontal=True, tri=None, hauteur=200,
                  couleurs={"Sans réassignation": TURQUOISE, "Avec réassignation": BLEU},
                  infobulles=infobulles_resume("reassignment_status", "Incidents"))


def graphique_delais(df):
    return barres(tranches_delai(df), "incidents", "tranche", "Incidents", "Délai de résolution",
                  tri=alt.SortField("ordre"), angle=0, hauteur=380)


def graphique_categories(df):
    if "category" not in df.columns:
        return None
    categories = repartition(df, "category", limite=15)
    return barres(categories, "incidents", "category", "Incidents", "Catégorie", horizontal=True, tri=None,
                  hauteur=380, gris=hors_metier(categories["category"]))


def graphique_equipes(df):
    equipes = sla_par_equipe(df)
    if equipes.empty:
        return None
    return barres(equipes, "sla_pct", "assignment_group", "Respect des SLA (%)", "Équipe", horizontal=True,
                  tri="-x", domaine=[0, 100], hauteur=400, gris=hors_metier(equipes["assignment_group"]),
                  infobulles=infobulles_resume("assignment_group", "Équipe"))


def png(graphique, largeur=640):
    """Image PNG d'un graphique Altair (pour le rapport Word), sur fond blanc."""
    spec = graphique.properties(width=largeur, background="#FFFFFF").to_dict()
    return vl_convert.vegalite_to_png(spec, scale=2)
