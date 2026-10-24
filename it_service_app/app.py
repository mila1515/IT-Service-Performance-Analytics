"""IT Service Performance : importer un CSV d'incidents et explorer la performance du service IT.

Lancer depuis la racine du dépôt : python -m streamlit run it_service_app/app.py (port 8510, voir .streamlit/config.toml)
Parcours : 1 Importer → 2 Vérifier → 3 Filtrer → 4 Indicateurs et graphiques → 5 Télécharger.
Ce fichier ne contient que l'interface ; les règles sont dans preparation.py et indicateurs.py.
Le fichier importé reste en mémoire de session : rien n'est écrit sur le disque.
"""
import altair as alt
import pandas as pd
import streamlit as st

from indicateurs import (CHAMP_PERIODE, FILTRES, MIN_INCIDENTS_EQUIPE, calculer_kpi, effet_reassignation,
                         filtrer, format_fr, lecture, plus_longs, plus_reassignes, recapitulatif_kpi, repartition,
                         sla_par_equipe, sla_par_mois, sla_par_priorite, tranches_delai, volume_par_mois)
from preparation import COLONNES_REQUISES, COLONNES_UTILES, FichierIncompatible, lire_csv, preparer

# KPI affichés en cartes ; les autres sont dans le tableau des définitions.
KPI_CARTES = ["Incidents uniques", "Incidents résolus", "Incidents ouverts", "Délai moyen de résolution",
              "Délai médian de résolution", "Respect des SLA", "Taux d'incidents réassignés"]


@st.cache_data(max_entries=2, show_spinner="Préparation des incidents…")
def charger(contenu):
    """Lecture + préparation, mises en cache pour ne pas les refaire à chaque filtre."""
    return preparer(lire_csv(contenu))


def barres(data, x, y, titre_x, titre_y, horizontal=False, tri=None, domaine=None, infobulles=None):
    """Diagramme en barres d'une seule série (x = valeur, y = catégorie), avec infobulle."""
    echelle = alt.Scale(domain=domaine) if domaine else alt.Undefined
    valeur = (alt.X if horizontal else alt.Y)(f"{x}:Q", title=titre_x, scale=echelle)
    categorie = (alt.Y if horizontal else alt.X)(f"{y}:N", title=titre_y, sort=tri)
    infobulles = infobulles or [alt.Tooltip(y, title=titre_y), alt.Tooltip(x, title=titre_x)]
    return alt.Chart(data).mark_bar(cornerRadiusEnd=4).encode(categorie, valeur, tooltip=infobulles)


def infobulles_resume(nom, titre):
    """Infobulle commune aux tableaux de resume() : incidents, SLA et délais."""
    return [alt.Tooltip(nom, title=titre), alt.Tooltip("incidents", title="Incidents"),
            alt.Tooltip("sla_pct", title="SLA (%)"), alt.Tooltip("resolution_moyenne_h", title="Délai moyen (h)"),
            alt.Tooltip("resolution_mediane_h", title="Délai médian (h)")]


# Libellés des colonnes produites par resume().
COLONNES_RESUME = {"incidents": "Incidents", "sla_pct": st.column_config.NumberColumn("SLA (%)", format="%.2f"),
                   "resolution_moyenne_h": "Délai moyen (h)", "resolution_mediane_h": "Délai médian (h)"}


st.set_page_config(page_title="IT Service Performance", page_icon=":material/support_agent:", layout="wide")
st.title("IT Service Performance")
st.caption("Importez un fichier d'incidents ServiceNow (journal d'événements ou table d'incidents) "
           "pour contrôler les données et suivre la performance du service, sans exécuter le notebook.")

# --- 1. Importer --------------------------------------------------------------------------------
st.header("1. Importer", divider="gray")
fichier = st.file_uploader("Fichier CSV d'incidents", type="csv",
                           help="Par exemple data/raw/incident_event_log.csv ou data/processed/incident_clean.csv.")
if fichier is None:
    with st.container(border=True):
        st.markdown(f"**Colonnes obligatoires :** {', '.join(f'`{c}`' for c in COLONNES_REQUISES)}")
        st.markdown("**Colonnes utiles** (sans elles, certains indicateurs sont indisponibles) :")
        st.dataframe(pd.DataFrame(COLONNES_UTILES.items(), columns=["colonne", "rôle"]), hide_index=True,
                     alt="Colonnes utiles et leur rôle")
    st.stop()

try:
    incidents, controles, infos = charger(fichier.getvalue())
except FichierIncompatible as erreur:
    st.error(str(erreur), title="Fichier incompatible", icon=":material/block:")
    st.stop()

# --- 2. Vérifier --------------------------------------------------------------------------------
st.header("2. Vérifier", divider="gray")
with st.container(horizontal=True):
    st.metric("Lignes lues", format_fr(infos["lignes"]), border=True)
    st.metric("Colonnes", format_fr(infos["colonnes"]), border=True)
    st.metric("Incidents uniques", format_fr(infos["incidents"]), border=True)
    st.metric("Lignes par incident", format_fr(infos["lignes_par_incident"]), border=True,
              help="Moyenne : 1 pour une table d'incidents, plus pour un journal d'événements.")
    debut_fichier, fin_fichier = infos["periode"]
    st.metric("Période couverte", "—" if pd.isna(debut_fichier) else f"{debut_fichier:%d/%m/%Y} – {fin_fichier:%d/%m/%Y}",
              border=True, help="Première et dernière date d'ouverture valides (opened_at).")
    st.metric("Format détecté", infos["format"].capitalize(), border=True)
if infos["format"] == "journal d'événements":
    st.info(f"Le fichier contient plusieurs lignes par incident ({format_fr(infos['lignes'])} lignes pour "
            f"{format_fr(infos['incidents'])} incidents). Les indicateurs portent sur le **dernier état connu** "
            "de chaque incident (sys_updated_at le plus récent), comme dans le notebook.", icon=":material/info:")
if infos["colonnes_absentes"]:
    st.warning("\n".join(f"- `{c}` : {role}" for c, role in infos["colonnes_absentes"].items()),
               title="Colonnes utiles absentes : les indicateurs concernés seront indisponibles",
               icon=":material/warning:")
formats = {c: f or "aucun format reconnu" for c, f in infos["formats_dates"].items()}
st.caption("Formats de dates reconnus : " + " · ".join(f"{c} = `{f}`" for c, f in formats.items()))

anomalies = controles[controles["valeur"] > 0]
st.subheader("Anomalies et exclusions qui influencent les calculs")
if anomalies.empty:
    st.success("Aucune anomalie détectée.", icon=":material/check_circle:")
else:
    st.dataframe(anomalies, hide_index=True, alt="Anomalies détectées et leur effet sur les calculs")
with st.expander("Tous les contrôles, y compris ceux à zéro"):
    st.dataframe(controles, hide_index=True, alt="Liste complète des contrôles")
with st.expander(f"Valeurs manquantes par colonne du fichier importé ({len(infos['manquants'])} colonnes concernées)"):
    st.caption("Comptées sur les lignes du fichier, avant la réduction au dernier état ; « ? » est une valeur manquante.")
    st.dataframe(infos["manquants"], hide_index=True, alt="Valeurs manquantes par colonne",
                 column_config={"valeurs_manquantes": "Valeurs manquantes",
                                "taux_manquant_pct": st.column_config.ProgressColumn(
                                    "Taux manquant (%)", format="%.2f", min_value=0, max_value=100)})

# --- 3. Filtrer ---------------------------------------------------------------------------------
st.header("3. Filtrer", divider="gray")
dates = incidents[CHAMP_PERIODE].dropna()
choix = {}
with st.container(border=True):
    colonnes = st.columns(len(FILTRES) + 1)
    with colonnes[0]:
        if dates.empty:
            debut = fin = None
            st.caption("Période : aucune date d'ouverture valide, filtre indisponible.")
        else:
            premier, dernier = dates.min().date(), dates.max().date()
            periode = st.date_input("Période d'ouverture", (premier, dernier), min_value=premier, max_value=dernier,
                                    format="DD/MM/YYYY", help="Filtre sur la date d'ouverture (opened_at).")
            debut, fin = (tuple(periode) + (dernier,))[:2] if periode else (premier, dernier)
            # Période complète : pas de filtre, pour garder les incidents sans date d'ouverture valide.
            if (debut, fin) == (premier, dernier):
                debut = fin = None
    for colonne, (champ, libelle) in zip(colonnes[1:], FILTRES.items()):
        with colonne:
            if champ in incidents.columns:
                options = sorted(incidents[champ].dropna().astype(str).unique())
                choix[champ] = st.multiselect(libelle, options, placeholder="Tous", key=f"filtre_{champ}")
            else:
                st.caption(f"{libelle} : colonne {champ} absente.")

selection = filtrer(incidents, debut, fin, choix)
actifs = ([f"période {debut:%d/%m/%Y} – {fin:%d/%m/%Y} (opened_at)"] if debut else []) + \
         [f"{FILTRES[c]} = {', '.join(v)}" for c, v in choix.items() if v]
description_filtres = " ; ".join(actifs) or "aucun filtre"
st.caption(f"**{format_fr(selection['number'].nunique())}** incidents sur {format_fr(len(incidents))} · "
           f"Filtres actifs : {description_filtres}")

# --- 4. Indicateurs et graphiques ---------------------------------------------------------------
st.header("4. Indicateurs", divider="gray")
kpis = calculer_kpi(selection)
if selection.empty:
    st.warning("Aucun incident ne correspond aux filtres choisis. Élargissez la période ou retirez un filtre.",
               title="Filtres sans résultat", icon=":material/filter_alt_off:")
else:
    par_nom = {k["indicateur"]: k for k in kpis}
    with st.container(horizontal=True):
        for nom in KPI_CARTES:
            k = par_nom[nom]
            st.metric(nom, format_fr(k["valeur"], k["unité"]), border=True,
                      help=k["indisponible"] or f"{k['définition']} Population : {k['population']}.")
    for k in kpis:
        if k["indisponible"]:
            st.warning(f"**{k['indicateur']}** : {k['indisponible']}", icon=":material/info:")
    with st.expander("Définitions, unités et populations de calcul", expanded=False):
        tableau = pd.DataFrame(kpis)
        tableau["valeur"] = [format_fr(k["valeur"], k["unité"]) for k in kpis]
        st.dataframe(tableau, hide_index=True, alt="Définition de chaque indicateur")

    messages = lecture(selection, kpis)
    if messages:
        with st.container(border=True):
            st.subheader("Lecture des résultats")
            st.markdown("\n".join(f"- {m}" for m in messages))
            st.caption("Messages calculés automatiquement sur la sélection filtrée, avec les seuils indiqués dans le "
                       "README. Ils montrent des liens, pas des causes : à confirmer avant de conclure.")

    sla_disponible = selection["sla_compliant"].notna().any()
    sans_sla = "Indisponible : pas de statut SLA exploitable (colonne made_sla absente ou vide)."

    gauche, droite = st.columns(2)
    with gauche.container(border=True):
        st.subheader("Évolution du nombre d'incidents")
        st.altair_chart(barres(volume_par_mois(selection), "incidents", "mois", "Incidents", "Mois d'ouverture"),
                        alt="Nombre d'incidents par mois d'ouverture")
        st.caption("Date utilisée : opened_at. Un mois avec peu d'incidents ne permet pas de conclure à une tendance.")
    with droite.container(border=True):
        st.subheader("Respect des SLA par mois")
        if sla_disponible:
            st.altair_chart(barres(sla_par_mois(selection), "sla_pct", "mois", "Respect des SLA (%)", "Mois d'ouverture",
                                   domaine=[0, 100], infobulles=infobulles_resume("mois", "Mois")),
                            alt="Taux de respect des SLA par mois d'ouverture")
            st.caption("Survolez une barre pour voir le nombre d'incidents : un taux calculé sur quelques incidents "
                       "varie fortement d'un mois à l'autre.")
        else:
            st.caption(sans_sla)

    gauche, droite = st.columns(2)
    with gauche.container(border=True):
        st.subheader("Respect des SLA par priorité")
        priorites = sla_par_priorite(selection)
        if priorites.empty:
            st.caption("Indisponible : colonne priority absente.")
        else:
            if sla_disponible:
                st.altair_chart(barres(priorites, "sla_pct", "priority", "Respect des SLA (%)", "Priorité",
                                       horizontal=True, tri="ascending", domaine=[0, 100],
                                       infobulles=infobulles_resume("priority", "Priorité")),
                                alt="Taux de respect des SLA par priorité")
            else:
                st.caption(sans_sla)
            st.dataframe(priorites, hide_index=True, alt="Volume, SLA et délais par priorité",
                         column_config={"priority": "Priorité", **COLONNES_RESUME})
    with droite.container(border=True):
        st.subheader("Effet des réassignations")
        reassignation = effet_reassignation(selection)
        if reassignation.empty:
            st.caption("Indisponible : colonne reassignment_count absente ou vide. Le nombre d'événements n'est pas "
                       "utilisé à la place.")
        else:
            st.altair_chart(barres(reassignation, "resolution_moyenne_h", "reassignment_status", "Délai moyen de résolution (h)",
                                   "Incidents", horizontal=True, tri=None,
                                   infobulles=infobulles_resume("reassignment_status", "Incidents")),
                            alt="Délai moyen de résolution avec et sans réassignation")
            st.dataframe(reassignation, hide_index=True, alt="Volume, SLA et délais avec et sans réassignation",
                         column_config={"reassignment_status": "Incidents", **COLONNES_RESUME})
            st.caption("Une réassignation signale souvent un mauvais routage initial ; la comparaison montre un lien, "
                       "pas une cause.")

    gauche, droite = st.columns(2)
    with gauche.container(border=True):
        st.subheader("Délais de résolution")
        st.altair_chart(barres(tranches_delai(selection), "incidents", "tranche", "Incidents", "Délai de résolution",
                               tri=alt.SortField("ordre")),
                        alt="Nombre d'incidents par tranche de délai de résolution")
        st.caption("Incidents avec des dates d'ouverture et de résolution valides. "
                   "La moyenne est tirée vers le haut par quelques incidents très longs : la médiane est plus représentative.")
    with droite.container(border=True):
        st.subheader("Répartition par catégorie")
        if "category" in selection.columns:
            st.altair_chart(barres(repartition(selection, "category", limite=15), "incidents", "category", "Incidents",
                                   "Catégorie", horizontal=True, tri=None), alt="Nombre d'incidents par catégorie")
            st.caption("Les 15 catégories les plus fréquentes ; « Inconnu » = catégorie non renseignée.")
        else:
            st.caption("Colonne category absente.")

    with st.container(border=True):
        st.subheader("Respect des SLA par équipe")
        equipes = sla_par_equipe(selection)
        if equipes.empty:
            st.caption("Indisponible : il faut les colonnes assignment_group et made_sla, et au moins une équipe avec "
                       f"{MIN_INCIDENTS_EQUIPE} incidents dans la sélection.")
        else:
            st.altair_chart(barres(equipes, "sla_pct", "assignment_group", "Respect des SLA (%)", "Équipe",
                                   horizontal=True, tri="-x", domaine=[0, 100],
                                   infobulles=infobulles_resume("assignment_group", "Équipe")),
                            alt="Taux de respect des SLA des équipes les plus chargées")
            st.caption(f"Les {len(equipes)} équipes les plus chargées (au moins {MIN_INCIDENTS_EQUIPE} incidents). "
                       "« Inconnu » = incidents sans équipe renseignée.")

    gauche, droite = st.columns(2)
    with gauche.container(border=True):
        st.subheader("Incidents les plus longs")
        longs = plus_longs(selection)
        if longs.empty:
            st.caption("Aucun incident avec un délai de résolution valide dans la sélection.")
        else:
            st.dataframe(longs, hide_index=True, alt="Les 25 incidents au délai de résolution le plus long",
                         column_config={"resolution_time_hours": "Délai de résolution (h)"})
            st.caption("Les 25 délais de résolution les plus longs : incidents à examiner un par un.")
    with droite.container(border=True):
        st.subheader("Incidents les plus réassignés")
        reassignes = plus_reassignes(selection)
        if reassignation.empty:
            st.caption("Indisponible : colonne reassignment_count absente ou vide.")
        elif reassignes.empty:
            st.caption("Aucun incident réassigné dans la sélection.")
        else:
            st.dataframe(reassignes, hide_index=True, alt="Incidents ayant le plus de réassignations",
                         column_config={"reassignment_count": "Réassignations",
                                        "resolution_time_hours": "Délai de résolution (h)"})
            st.caption("Les 20 incidents les plus réassignés.")

# --- 5. Télécharger -----------------------------------------------------------------------------
st.header("5. Télécharger", divider="gray")
st.caption("Les tables d'incidents gardent les colonnes et l'ordre de data/processed/incident_clean.csv, "
           "le fichier lu par Power BI. Les noms de fichiers sont différents : rien n'est écrasé.")
with st.container(horizontal=True):
    st.download_button("Table d'incidents préparée", lambda: incidents.to_csv(index=False),
                       file_name="it_service_incidents_prepares.csv", mime="text/csv",
                       icon=":material/download:", on_click="ignore")
    st.download_button("Données filtrées", lambda: selection.to_csv(index=False),
                       file_name="it_service_incidents_filtres.csv", mime="text/csv",
                       icon=":material/filter_alt:", on_click="ignore", disabled=selection.empty)
    st.download_button("Récapitulatif des KPI",
                       lambda: recapitulatif_kpi(kpis, description_filtres).to_csv(index=False).encode("utf-8-sig"),
                       file_name="it_service_kpi.csv", mime="text/csv", icon=":material/table_chart:",
                       on_click="ignore")
