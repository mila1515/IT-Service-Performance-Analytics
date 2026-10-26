"""IT Service Performance : importer un CSV d'incidents et explorer la performance du service IT.

Lancer depuis la racine du dépôt : python -m streamlit run it_service_app/app.py (port 8510, voir .streamlit/config.toml)
Parcours : 1 Importer → 2 Vérifier → 3 Filtrer → 4 Indicateurs et graphiques → 5 Télécharger.
Ce fichier ne contient que l'interface ; les règles sont dans preparation.py et indicateurs.py,
les graphiques dans graphiques.py et le rapport Word dans rapport.py.
Le fichier importé reste en mémoire de session : rien n'est écrit sur le disque.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

from graphiques import (graphique_categories, graphique_delais, graphique_equipes, graphique_reassignation,
                        graphique_sla_mois, graphique_sla_priorite, graphique_volume)
from indicateurs import (CHAMP_PERIODE, FILTRES, MIN_INCIDENTS_EQUIPE, calculer_kpi, effet_reassignation,
                         filtrer, format_fr, lecture, plus_longs, plus_reassignes, recapitulatif_kpi,
                         sla_par_equipe, sla_par_priorite)
from preparation import (COLONNES_REQUISES, COLONNES_UTILES, OPTIONS, FichierIncompatible, appliquer_options,
                         lire_csv, preparer)
from rapport import rapport_word

LOGO = Path(__file__).parent / "assets" / "logo.svg"
# KPI en cartes, deux lignes de quatre ; les autres sont dans le tableau des définitions.
KPI_CARTES = [["Incidents uniques", "Incidents résolus", "Incidents ouverts", "Respect des SLA"],
              ["Délai moyen de résolution", "Délai médian de résolution", "Taux d'incidents réassignés",
               "Réassignations moyennes"]]


@st.cache_data(max_entries=2, show_spinner="Préparation des incidents…")
def charger(contenu):
    """Lecture + préparation, mises en cache pour ne pas les refaire à chaque filtre."""
    return preparer(lire_csv(contenu))


def etape(icone, numero, titre):
    st.header(f":material/{icone}: {numero} · {titre}", divider="blue")


def nombre(titre):
    """Colonne numérique affichée selon la langue du navigateur (1 234,57 en français)."""
    return st.column_config.NumberColumn(titre, format="localized")


# Libellés français des tableaux : colonnes de resume(), des contrôles et des listes d'incidents.
COLONNES_RESUME = {"incidents": nombre("Incidents"), "sla_pct": nombre("SLA (%)"),
                   "resolution_moyenne_h": nombre("Délai moyen (h)"), "resolution_mediane_h": nombre("Délai médian (h)")}
COLONNES_CONTROLES = {"contrôle": "Contrôle", "valeur": nombre("Valeur"), "effet sur les calculs": "Effet sur les calculs"}
COLONNES_INCIDENTS = {"number": "Incident", "assignment_group": "Équipe", "category": "Catégorie",
                      "priority": "Priorité", "incident_state": "État", "reassignment_count": nombre("Réassignations"),
                      "resolution_time_hours": nombre("Délai de résolution (h)")}


st.set_page_config(page_title="IT Service Performance", page_icon=str(LOGO), layout="wide")
# Le thème ne colore pas les cartes : cartes (clé « carte_… ») et chiffres clés en blanc sur le fond gris-bleu.
st.html("<style>[class*='st-key-carte_'], [data-testid='stMetric'] { background-color: #FFFFFF; }</style>")

with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    st.image(str(LOGO), width=76)
    with st.container(gap=None):
        st.title("IT Service Performance", anchor=False)
        st.caption("Contrôler un export d'incidents ServiceNow et suivre la performance du support IT : "
                   "volumes, délais de résolution, respect des SLA et réassignations.")

# --- 1. Importer --------------------------------------------------------------------------------
etape("upload_file", 1, "Importer")
fichier = st.file_uploader("Fichier CSV d'incidents", type="csv",
                           help="Par exemple data/raw/incident_event_log.csv ou data/processed/incident_clean.csv.")
if fichier is None:
    with st.container(border=True, key="carte_colonnes"):
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
etape("fact_check", 2, "Vérifier")
debut_fichier, fin_fichier = infos["periode"]
cartes = st.columns([1, 1, 1, 1, 2])
cartes[0].metric("Lignes lues", format_fr(infos["lignes"]), border=True)
cartes[1].metric("Colonnes", format_fr(infos["colonnes"]), border=True)
cartes[2].metric("Incidents uniques", format_fr(infos["incidents"]), border=True)
cartes[3].metric("Lignes par incident", format_fr(infos["lignes_par_incident"]), border=True,
                 help="Moyenne : 1 pour une table d'incidents, plus pour un journal d'événements.")
cartes[4].metric("Période couverte",
                 "—" if pd.isna(debut_fichier) else f"{debut_fichier:%d/%m/%Y} – {fin_fichier:%d/%m/%Y}",
                 border=True, help="Première et dernière date d'ouverture valides (opened_at).")
if infos["format"] == "journal d'événements":
    st.info(f"{format_fr(infos['lignes'])} lignes pour {format_fr(infos['incidents'])} incidents. Les indicateurs "
            "portent sur le **dernier état connu** de chaque incident (sys_updated_at le plus récent).",
            title="Journal d'événements détecté", icon=":material/timeline:")
else:
    st.success("Une ligne par incident : le fichier est utilisé tel quel.", title="Table d'incidents détectée",
               icon=":material/table_rows:")
if infos["colonnes_absentes"]:
    st.warning("\n".join(f"- `{c}` : {role}" for c, role in infos["colonnes_absentes"].items()),
               title="Colonnes utiles absentes : les indicateurs concernés seront indisponibles",
               icon=":material/warning:")

anomalies = controles[controles["valeur"] > 0]
with st.container(border=True, key="carte_anomalies"):
    st.subheader(":material/rule: Anomalies et exclusions qui influencent les calculs", anchor=False)
    if anomalies.empty:
        st.success("Aucune anomalie détectée.", icon=":material/check_circle:")
    else:
        st.dataframe(anomalies, hide_index=True, alt="Anomalies détectées et leur effet sur les calculs",
                     column_config=COLONNES_CONTROLES)
    with st.expander("Tous les contrôles, y compris ceux à zéro"):
        st.dataframe(controles, hide_index=True, alt="Liste complète des contrôles", column_config=COLONNES_CONTROLES)
    with st.expander(f"Valeurs manquantes par colonne du fichier importé ({len(infos['manquants'])} colonnes concernées)"):
        st.caption("Comptées sur les lignes du fichier, avant la réduction au dernier état ; « ? » est une valeur manquante.")
        st.dataframe(infos["manquants"], hide_index=True, alt="Valeurs manquantes par colonne",
                     column_config={"colonne": "Colonne", "type": "Type", "valeurs_manquantes": nombre("Valeurs manquantes"),
                                    "taux_manquant_pct": st.column_config.ProgressColumn(
                                        "Taux manquant (%)", format="%.2f", min_value=0, max_value=100)})
    with st.expander("Formats de dates reconnus"):
        formats = {c: f or "aucun format reconnu" for c, f in infos["formats_dates"].items()}
        st.dataframe(pd.DataFrame(formats.items(), columns=["colonne", "format"]), hide_index=True,
                     alt="Format reconnu pour chaque colonne de dates")

with st.container(border=True, key="carte_options"):
    st.subheader(":material/tune: Options de nettoyage (facultatives)", anchor=False)
    st.caption("Décochées, les résultats suivent les règles de référence (identiques au rapport Power BI). "
               "Cochez une option pour en tester l'effet sur tous les indicateurs, graphiques et exports.")
    colonnes_options = st.columns(2)
    choisies = [option for i, (option, libelle) in enumerate(OPTIONS.items())
                if colonnes_options[i % 2].checkbox(libelle, key=f"option_{option}")]
    incidents, effets_options = appliquer_options(incidents, choisies)
    if effets_options:
        st.dataframe(pd.DataFrame(effets_options), hide_index=True, alt="Effet des options de nettoyage cochées",
                     column_config={"option": "Option", "incidents concernés": nombre("Incidents concernés"),
                                    "effet": "Effet"})
        st.warning("Les résultats ne sont plus ceux des règles de référence : ils peuvent différer du rapport "
                   "Power BI.", icon=":material/info:")

# --- 3. Filtrer ---------------------------------------------------------------------------------
etape("filter_alt", 3, "Filtrer")
dates = incidents[CHAMP_PERIODE].dropna()
choix = {}
with st.container(border=True, key="carte_filtres"):
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
if effets_options:
    description_filtres += " · options : " + " ; ".join(e["option"] for e in effets_options)
st.caption(f":material/info: **{format_fr(selection['number'].nunique())}** incidents sur "
           f"{format_fr(len(incidents))} · Filtres actifs : {description_filtres}")

# --- 4. Indicateurs et graphiques ---------------------------------------------------------------
etape("monitoring", 4, "Indicateurs")
kpis = calculer_kpi(selection)
if selection.empty:
    st.warning("Aucun incident ne correspond aux filtres choisis. Élargissez la période ou retirez un filtre.",
               title="Filtres sans résultat", icon=":material/filter_alt_off:")
else:
    par_nom = {k["indicateur"]: k for k in kpis}
    for ligne in KPI_CARTES:
        for colonne, nom in zip(st.columns(len(ligne)), ligne):
            k = par_nom[nom]
            colonne.metric(nom, format_fr(k["valeur"], k["unité"]), border=True,
                           help=k["indisponible"] or f"{k['définition']} Population : {k['population']}.")
    for k in kpis:
        if k["indisponible"]:
            st.warning(f"**{k['indicateur']}** : {k['indisponible']}", icon=":material/info:")
    with st.expander("Définitions, unités et populations de calcul", icon=":material/menu_book:"):
        tableau = pd.DataFrame(kpis)
        tableau["valeur"] = [format_fr(k["valeur"], k["unité"]) for k in kpis]
        st.dataframe(tableau, hide_index=True, alt="Définition de chaque indicateur")

    messages = lecture(selection, kpis)
    if messages:
        with st.container(border=True, key="carte_lecture"):
            st.subheader(":material/lightbulb: Lecture des résultats", anchor=False)
            st.markdown("\n".join(f"- {m}" for m in messages))
            st.caption("Messages calculés automatiquement sur la sélection filtrée. Ils montrent des liens, "
                       "pas des causes : à confirmer avant de conclure.")

    sla_disponible = selection["sla_compliant"].notna().any()
    sans_sla = "Indisponible : pas de statut SLA exploitable (colonne made_sla absente ou vide)."

    gauche, droite = st.columns(2)
    with gauche.container(border=True, key="carte_volume"):
        st.subheader("Évolution du nombre d'incidents", anchor=False)
        st.altair_chart(graphique_volume(selection), alt="Nombre d'incidents par mois d'ouverture")
        st.caption("Date utilisée : opened_at. Un mois avec peu d'incidents ne permet pas de conclure à une tendance.")
    with droite.container(border=True, key="carte_sla_mois"):
        st.subheader("Respect des SLA par mois", anchor=False)
        if sla_disponible:
            st.altair_chart(graphique_sla_mois(selection), alt="Taux de respect des SLA par mois d'ouverture")
            st.caption("Survolez une barre pour voir le nombre d'incidents : un taux calculé sur quelques incidents "
                       "varie fortement d'un mois à l'autre.")
        else:
            st.caption(sans_sla)

    gauche, droite = st.columns(2)
    with gauche.container(border=True, key="carte_priorite", height="stretch"):
        st.subheader("Respect des SLA par priorité", anchor=False)
        priorites = sla_par_priorite(selection)
        if priorites.empty:
            st.caption("Indisponible : colonne priority absente.")
        else:
            if sla_disponible:
                st.altair_chart(graphique_sla_priorite(selection), alt="Taux de respect des SLA par priorité")
            else:
                st.caption(sans_sla)
            st.dataframe(priorites, hide_index=True, alt="Volume, SLA et délais par priorité",
                         column_config={"priority": "Priorité", **COLONNES_RESUME})
    with droite.container(border=True, key="carte_reassignation", height="stretch"):
        st.subheader("Effet des réassignations", anchor=False)
        reassignation = effet_reassignation(selection)
        if reassignation.empty:
            st.caption("Indisponible : colonne reassignment_count absente ou vide. Le nombre d'événements n'est pas "
                       "utilisé à la place.")
        else:
            st.altair_chart(graphique_reassignation(selection),
                            alt="Délai moyen de résolution avec et sans réassignation")
            st.dataframe(reassignation, hide_index=True, alt="Volume, SLA et délais avec et sans réassignation",
                         column_config={"reassignment_status": "Réassignation", **COLONNES_RESUME})
            st.caption("Une réassignation signale souvent un mauvais routage initial ; la comparaison montre un lien, "
                       "pas une cause.")

    gauche, droite = st.columns(2)
    with gauche.container(border=True, key="carte_delais", height="stretch"):
        st.subheader("Délais de résolution", anchor=False)
        st.altair_chart(graphique_delais(selection), alt="Nombre d'incidents par tranche de délai de résolution")
        st.caption("Incidents avec des dates d'ouverture et de résolution valides. "
                   "La moyenne est tirée vers le haut par quelques incidents très longs : la médiane est plus représentative.")
    with droite.container(border=True, key="carte_categorie", height="stretch"):
        st.subheader("Répartition par catégorie", anchor=False)
        if "category" in selection.columns:
            st.altair_chart(graphique_categories(selection), alt="Nombre d'incidents par catégorie")
            st.caption("Les 15 catégories les plus fréquentes. En gris : « Inconnu » (catégorie non renseignée) "
                       "et « Autres » (les catégories suivantes, regroupées).")
        else:
            st.caption("Colonne category absente.")

    with st.container(border=True, key="carte_equipes"):
        st.subheader("Respect des SLA par équipe", anchor=False)
        equipes = sla_par_equipe(selection)
        if equipes.empty:
            st.caption("Indisponible : il faut les colonnes assignment_group et made_sla, et au moins une équipe avec "
                       f"{MIN_INCIDENTS_EQUIPE} incidents dans la sélection.")
        else:
            st.altair_chart(graphique_equipes(selection), alt="Taux de respect des SLA des équipes les plus chargées")
            st.caption(f"Les {len(equipes)} équipes les plus chargées (au moins {MIN_INCIDENTS_EQUIPE} incidents). "
                       "En gris : « Inconnu », les incidents sans équipe renseignée.")

    gauche, droite = st.columns(2)
    with gauche.container(border=True, key="carte_longs", height="stretch"):
        st.subheader(":material/hourglass_bottom: Incidents les plus longs", anchor=False)
        longs = plus_longs(selection)
        if longs.empty:
            st.caption("Aucun incident avec un délai de résolution valide dans la sélection.")
        else:
            st.dataframe(longs, hide_index=True, alt="Les 25 incidents au délai de résolution le plus long",
                         column_config=COLONNES_INCIDENTS)
            st.caption("Les 25 délais de résolution les plus longs : incidents à examiner un par un.")
    with droite.container(border=True, key="carte_reassignes", height="stretch"):
        st.subheader(":material/swap_horiz: Incidents les plus réassignés", anchor=False)
        reassignes = plus_reassignes(selection)
        if reassignation.empty:
            st.caption("Indisponible : colonne reassignment_count absente ou vide.")
        elif reassignes.empty:
            st.caption("Aucun incident réassigné dans la sélection.")
        else:
            st.dataframe(reassignes, hide_index=True, alt="Incidents ayant le plus de réassignations",
                         column_config=COLONNES_INCIDENTS)
            st.caption("Les 20 incidents les plus réassignés.")

# --- 5. Télécharger -----------------------------------------------------------------------------
etape("download", 5, "Télécharger")
with st.container(border=True, key="carte_exports"):
    st.markdown(
        "- **Rapport d'analyse** (Word, à imprimer ou partager) : le fichier, son nettoyage, les indicateurs, "
        "les graphiques et l'interprétation.\n"
        "- **Données nettoyées** (CSV) : une ligne par incident, après contrôle et nettoyage, sur toute la période.\n"
        "- **Données nettoyées et filtrées** (CSV) : la même table, limitée aux filtres de l'étape 3.\n"
        "- **Indicateurs** (CSV) : chaque KPI avec sa valeur, sa définition et le périmètre utilisé.")
    with st.container(horizontal=True):
        st.download_button("Rapport d'analyse (Word)",
                           lambda: rapport_word(fichier.name, infos, controles, incidents, selection, kpis,
                                                effets_options, description_filtres),
                           file_name="rapport_analyse_incidents_it.docx", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           icon=":material/description:", on_click="ignore")
        st.download_button("Données nettoyées", lambda: incidents.to_csv(index=False),
                           file_name="it_service_incidents_nettoyes.csv", mime="text/csv",
                           icon=":material/cleaning_services:", on_click="ignore")
        st.download_button("Données nettoyées et filtrées", lambda: selection.to_csv(index=False),
                           file_name="it_service_incidents_filtres.csv", mime="text/csv",
                           icon=":material/filter_alt:", on_click="ignore", disabled=selection.empty)
        st.download_button("Indicateurs",
                           lambda: recapitulatif_kpi(kpis, description_filtres).to_csv(index=False).encode("utf-8-sig"),
                           file_name="it_service_kpi.csv", mime="text/csv", icon=":material/table_chart:",
                           on_click="ignore")
