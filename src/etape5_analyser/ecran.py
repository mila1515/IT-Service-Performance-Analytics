"""Étape 5 (Analyser) : comparer des groupes, mesurer un délai, suivre une évolution, puis continuer ailleurs.

Entrées en session : `validation` (données corrigées, types). Rien n'est modifié : l'utilisateur
choisit les colonnes, l'outil calcule et décrit. Sorties : `analyses` (résumés repris par le rapport
complet), dossier « données + notebook » (ZIP) et rapport complet (HTML ou Word).
"""
import streamlit as st

from src.config import LIBELLE_MANQUANT
from src.core.dessins import classement, periodes
from src.core.session import aller, cached
from src.core.texte import nombre_lisible
from src.etape4_visualiser.ecran import section_rapport
from src.etape4_visualiser.preparation import prepare
from src.etape5_analyser.calculs import (STATISTIQUES, comparer, de, delais, duree, duree_lisible, evolution,
                                         sections_possibles, une_ligne_par, unite_comptee)
from src.etape5_analyser.exports import export_donnees, fichiers_donnees, nom_colonne_delai
from src.etape5_analyser.resumes import (PRUDENCE_COMPARER, PRUDENCE_EVOLUTION, prudence_delai, resume_comparaison,
                                         resume_delai, resume_evolution)

AUCUN = "(aucun)"


def _par_type(roles, role):
    return [c for c, r in roles.items() if r == role]


def _constats(cle, constats, prudence):
    with st.container(border=True, key=f"carte_constats_{cle}"):
        st.markdown("**Ce que montrent les chiffres**")
        st.markdown("\n".join(f"- {c}" for c in constats) or "- Rien de particulier à signaler.")
        st.caption(prudence)


def _identifiant(data, roles):
    """Case « Compter chaque … une seule fois », cochée par défaut si l'identifiant se répète."""
    identifiants = _par_type(roles, "Identifiant")
    if not identifiants:
        return None
    colonne = identifiants[0]
    if len(identifiants) > 1:
        colonne = st.selectbox("Identifiant", identifiants, key="w_analyse_identifiant",
                               help="La colonne qui désigne un même élément sur plusieurs lignes.")
    repete = bool(data[colonne].duplicated().any())
    une_fois = st.checkbox(f"Compter chaque {colonne} une seule fois (sa dernière ligne)", value=repete,
                           key=f"w_analyse_une_fois_{colonne}",
                           help="Utile quand une même valeur revient sur plusieurs lignes (une ligne par mise à jour).")
    return colonne if une_fois else None


def _section_comparer(unites, roles, unite, resumes):
    with st.container(border=True, key="carte_analyse_comparer"):
        st.subheader("Comparer des groupes", anchor=False)
        categories, mesures = _par_type(roles, "Catégorie"), _par_type(roles, "Mesure")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            groupe = st.selectbox("Groupes (une catégorie)", categories, key="w_analyse_groupe")
            options = ["nombre"] + (["moyenne", "mediane"] if mesures else [])
            statistique = st.segmented_control("Ce qu'on compte", options, default="nombre", required=True,
                                               key="w_analyse_statistique",
                                               format_func=lambda s: f"Nombre {de(unite)}" if s == "nombre" else f"{STATISTIQUES[s]} d'un nombre")
            mesure = st.selectbox("Nombre", mesures, key="w_analyse_mesure") if statistique != "nombre" else None
        resultat = cached(comparer, unites, groupe, statistique, mesure, unite)
        gauche, droite = st.columns([1.25, 1])
        with gauche:
            if resultat["graphique"] is not None:
                titre = "Nombre" if statistique == "nombre" else STATISTIQUES[statistique]
                st.altair_chart(classement(resultat["graphique"], titre), alt=f"{titre} par {groupe}")
                st.caption(f"{min(len(resultat['tableau']), 10)} premiers groupes sur {len(resultat['tableau'])}"
                           + (" · plus clair : moins de 20 valeurs" if statistique != "nombre" else ""))
        with droite:
            _constats("comparer", resultat["constats"], PRUDENCE_COMPARER)
    resumes.append(resume_comparaison(resultat, groupe, statistique, mesure, unite))
    return groupe, statistique, mesure


def _section_delai(unites, roles, unite, groupe_defaut, resumes):
    with st.container(border=True, key="carte_analyse_delai"):
        st.subheader("Mesurer un délai", anchor=False)
        dates, categories = _par_type(roles, "Date"), _par_type(roles, "Catégorie")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            debut = st.selectbox("Date de début", dates, index=0, key="w_analyse_debut")
            fins = [d for d in dates if d != debut]
            # Par défaut, la dernière date du fichier : souvent la fin d'un traitement (livraison, clôture…).
            fin = st.selectbox("Date de fin", fins, index=len(fins) - 1, key="w_analyse_fin")
            choix_groupes = [AUCUN] + categories
            groupe = st.selectbox("Par", choix_groupes, key="w_analyse_par",
                                  index=choix_groupes.index(groupe_defaut) if groupe_defaut in choix_groupes else 0)
            unite_temps = st.segmented_control("Unité", ["heures", "jours"], default="jours", required=True,
                                               key="w_analyse_unite", format_func=str.capitalize)
        groupe = None if groupe == AUCUN else groupe
        resultat = cached(delais, unites, debut, fin, groupe, unite_temps, unite)
        with st.container(horizontal=True):
            st.metric("Délai médian, tous", duree_lisible(resultat["mediane"], unite_temps) if resultat["mediane"] is not None else "—",
                      border=True)
            st.metric("Délais calculables", f"{nombre_lisible(resultat['calculables'])} / {nombre_lisible(resultat['total'])}", border=True)
            if resultat["tableau"] is not None:
                comparables = int((~resultat["tableau"]["Fragile"] & (resultat["tableau"]["Groupe"] != LIBELLE_MANQUANT)).sum())
                st.metric("Groupes comparés (≥ 20)", nombre_lisible(comparables), border=True)
        gauche, droite = st.columns([1.25, 1])
        with gauche:
            if resultat["graphique"] is not None and len(resultat["graphique"]):
                st.altair_chart(classement(resultat["graphique"], "Délai médian"), alt=f"Délai médian par {groupe}")
                st.caption(f"Délai médian par groupe · « · n » = nombre de {unite} du groupe")
        with droite:
            _constats("delai", resultat["constats"], prudence_delai(unite))
    resumes.append(resume_delai(resultat, debut, fin, groupe, unite_temps, unite))
    return debut, fin, unite_temps


def _section_evolution(unites, roles, unite, resumes):
    with st.container(border=True, key="carte_analyse_evolution"):
        st.subheader("Évolution dans le temps", anchor=False)
        dates, categories = _par_type(roles, "Date"), _par_type(roles, "Catégorie")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            date = st.selectbox("Date", dates, key="w_analyse_date")
            groupe = st.selectbox("Pour", [AUCUN] + categories, key="w_analyse_evol_groupe",
                                  format_func=lambda g: "Toutes les lignes" if g == AUCUN else f"une valeur de {g}")
            valeur = None
            if groupe != AUCUN:
                valeurs = unites[groupe].astype("string").fillna(LIBELLE_MANQUANT).value_counts().index.tolist()[:50]
                valeur = st.selectbox("Valeur", valeurs, key="w_analyse_evol_valeur")
        resultat = cached(evolution, unites, date, None if groupe == AUCUN else groupe, valeur, unite)
        if resultat is None:
            st.info(f"Aucune date lisible dans {date}.", icon=":material/info:")
            return date
        gauche, droite = st.columns([1.25, 1])
        with gauche:
            st.altair_chart(periodes(resultat["donnees"], unite.capitalize()), alt=f"Nombre {de(unite)} par {resultat['unite']}")
        with droite:
            _constats("evolution", resultat["constats"], PRUDENCE_EVOLUTION)
    resumes.append(resume_evolution(resultat, date, None if groupe == AUCUN else groupe, valeur, unite))
    return date


def _section_exports(data, roles, nom, reglages, validation):
    with st.container(border=True, key="carte_analyse_exports"):
        st.subheader("Télécharger votre travail", anchor=False)
        st.caption("Rien n'est enregistré en ligne : téléchargez avant de fermer la page. Votre fichier d'origine n'a pas été modifié.")
        avec_delai = bool(reglages.get("debut") and reglages.get("fin"))
        colonne = nom_colonne_delai(reglages["debut"], reglages["fin"], reglages["unite_temps"]) if avec_delai else None
        base = nom.rsplit(".", 1)[0]

        def delai():
            return (colonne, duree(data, reglages["debut"], reglages["fin"], reglages["unite_temps"])) if avec_delai else None

        def dossier_zip():
            return export_donnees(data, roles, nom, reglages, delai())

        def dossier_fichiers():
            return fichiers_donnees(data, roles, nom, reglages, delai())

        gauche, droite = st.columns(2)
        with gauche, st.container(border=True, key="carte_analyse_rapport"):
            st.markdown("**Rapport complet**")
            st.caption("Tout le parcours, de l'import aux analyses.")
            section_rapport(validation, dossier_fichiers)
        with droite, st.container(border=True, key="carte_analyse_donnees"):
            st.markdown("**Données et notebook**")
            st.caption("Les données corrigées (CSV) et un notebook Jupyter, dans un ZIP.")
            st.download_button("Données + notebook (ZIP)", dossier_zip, f"{base}_donnees_et_notebook.zip", "application/zip",
                               type="primary", icon=":material/folder_zip:", on_click="ignore")


def ecran_analyser():
    """Écran de l'étape 5."""
    etat = st.session_state
    validation = etat.get("validation")
    st.title("Analyser vos données", anchor=False)
    if validation is None:
        st.info("Validez d'abord vos corrections à l'étape Corriger, même si vous ne changez rien.", icon=":material/info:")
        st.button("Aller à l'étape Corriger", type="primary", icon=":material/arrow_back:", on_click=aller, args=("Corriger",))
        return
    st.caption("Vous choisissez les colonnes, l'outil calcule, classe et décrit ce que montrent les chiffres. "
               "Il ne donne pas les causes : une différence se vérifie avec ce que vous savez du métier.")
    roles = {d["Colonne"]: d["Rôle"] for d in validation["plan"]["dictionary"]}
    dayfirst = {col: valeur == "jour" for col, valeur in validation["choix"].get("dates", {}).items()}
    data, _ = cached(prepare, validation["cleaned"], roles, dayfirst)
    possibles = sections_possibles(roles)
    if not any(possibles.values()):
        st.info("Aucune analyse possible : il faut au moins une colonne de type Catégorie ou Date (étape Comprendre).",
                icon=":material/info:")
        return
    identifiant = _identifiant(data, roles)
    unites = cached(une_ligne_par, data, identifiant)
    unite = unite_comptee(identifiant)
    reglages = {"identifiant": identifiant, "groupe": None, "statistique": None, "mesure": None,
                "debut": None, "fin": None, "unite_temps": "jours", "date": None}
    resumes = []
    if possibles["comparer"]:
        reglages["groupe"], reglages["statistique"], reglages["mesure"] = _section_comparer(unites, roles, unite, resumes)
    else:
        st.info("Comparer des groupes : il faut une colonne de type Catégorie.", icon=":material/info:")
    if possibles["delai"]:
        reglages["debut"], reglages["fin"], reglages["unite_temps"] = _section_delai(unites, roles, unite, reglages["groupe"], resumes)
    else:
        st.info("Mesurer un délai : il faut deux colonnes de type Date.", icon=":material/info:")
    if possibles["evolution"]:
        reglages["date"] = _section_evolution(unites, roles, unite, resumes)
    # Reprises par le rapport complet ; effacées à chaque nouvelle validation (étape Corriger).
    etat.analyses = resumes
    _section_exports(data, roles, etat.source["nom"], reglages, validation)
    st.button("Retour aux graphiques de contrôle", icon=":material/arrow_back:", on_click=aller, args=("Visualiser",))
