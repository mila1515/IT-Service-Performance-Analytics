"""Étape 4 (Visualiser et exporter) : contrôler en graphiques que les données corrigées sont plausibles, puis les remettre.

Entrées en session : `validation` (résultat validé à l'étape 3), `graphiques_ajoutes`, `notes`.
Sorties : téléchargements (données corrigées, lignes écartées, rapport qualité, archive).
Les graphiques servent au contrôle avant l'analyse métier, pas à en tirer des conclusions.
"""
from datetime import datetime, timezone
from functools import partial

import streamlit as st

from src.core.dessins import dessiner
from src.core.session import aller, cached
from src.etape2_comprendre.ecran import points_courants
from src.etape3_corriger.correction import decisions, phrases_journal
from src.etape4_visualiser.controles import comparaison, distribution, evolution, graphiques_controle, repartition
from src.etape4_visualiser.export import archive_projet, csv_bytes, rapport_qualite, rejets_lisibles
from src.etape4_visualiser.preparation import prepare

QUESTIONS = {
    "repartition": ("Comment se répartit une colonne", "Ex. : combien de lignes par catégorie"),
    "temps": ("Comment ça évolue dans le temps", "Ex. : nombre de lignes par mois"),
    "comparer": ("Comparer des groupes", "Ex. : moyenne d'un nombre par catégorie"),
}


def _roles(validation):
    return {d["Colonne"]: d["Rôle"] for d in validation["plan"]["dictionary"]}


def _graphique_ajoute(data, roles, spec, ignorees):
    colonne = spec["colonne"]
    if spec["question"] == "temps":
        return evolution(data, colonne)
    if spec["question"] == "comparer":
        return comparaison(data, spec["groupe"], colonne, ignorees.get(colonne, 0))
    return distribution(data, colonne, ignorees.get(colonne, 0)) if roles[colonne] == "Mesure" else repartition(data, colonne)


def _carte(graphique, retirer=None):
    with st.container(border=True, height="stretch"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{graphique['titre']}**")
            if retirer is not None:
                st.button("Retirer", key=f"w_ajout_retirer_{retirer}", type="tertiary", icon=":material/close:",
                          on_click=_retirer, args=(retirer,))
        st.caption(graphique["sous_titre"])
        st.altair_chart(dessiner(graphique), alt=f"{graphique['titre']}. {' '.join(graphique['a_retenir'])}")
        st.markdown("**À retenir :** " + " ".join(graphique["a_retenir"]))


def _retirer(index):
    etat = st.session_state
    etat.graphiques_ajoutes = [g for i, g in enumerate(etat.graphiques_ajoutes) if i != index]


def _ajouter(spec):
    st.session_state.graphiques_ajoutes = [*st.session_state.graphiques_ajoutes, spec]


def _section_ajout(roles):
    with st.container(border=True):
        st.subheader("Ajouter un graphique", anchor=False)
        question = st.segmented_control("Que voulez-vous voir ?", list(QUESTIONS), key="w_ajout_question",
                                        format_func=lambda q: QUESTIONS[q][0])
        if question is None:
            st.caption(" · ".join(f"{titre} — {exemple}" for titre, exemple in QUESTIONS.values()))
            return
        par_role = {role: [c for c, r in roles.items() if r == role] for role in ("Catégorie", "Mesure", "Date", "Identifiant")}
        spec = {"question": question}
        with st.container(horizontal=True, vertical_alignment="bottom"):
            if question == "temps":
                choix = par_role["Date"]
                spec["colonne"] = st.selectbox("Colonne de date", choix, key="w_ajout_date") if choix else None
            elif question == "comparer":
                spec["groupe"] = st.selectbox("Groupes à comparer", par_role["Catégorie"], key="w_ajout_groupe") if par_role["Catégorie"] else None
                spec["colonne"] = st.selectbox("Nombre à comparer", par_role["Mesure"], key="w_ajout_mesure") if par_role["Mesure"] else None
            else:
                choix = par_role["Catégorie"] + par_role["Mesure"]
                spec["colonne"] = st.selectbox("Colonne", choix, key="w_ajout_colonne") if choix else None
            manque = spec.get("colonne") is None or (question == "comparer" and spec.get("groupe") is None)
            st.button("Ajouter ce graphique", type="primary", icon=":material/add_chart:", disabled=manque,
                      on_click=_ajouter, args=(spec,))
        if manque:
            st.caption("Aucune colonne compatible : vérifiez les rôles à l'étape Comprendre.")


def _section_export(validation):
    etat = st.session_state
    with st.container(border=True):
        st.subheader("Télécharger votre travail", anchor=False)
        st.caption("Rien n'est enregistré en ligne : téléchargez avant de fermer la page. Votre fichier d'origine n'a pas été modifié.")
        notes = st.text_area("Ce que je retiens (facultatif)", value=etat.get("notes", ""), key="w_notes",
                             placeholder="Par exemple : la catégorie A est la plus fréquente ; vérifier avec l'équipe "
                                         "si les lignes identiques sont de vraies lignes.")
        etat.notes = notes
        source = etat.source
        rapport = partial(rapport_qualite, source["nom"], etat.raw.shape, source["empreinte"],
                          decisions(points_courants(), validation["choix"]), phrases_journal(validation["log"]),
                          validation["resultat"], notes)
        base = source["nom"].rsplit(".", 1)[0]
        with st.container(horizontal=True):
            # Fichiers générés au clic seulement : aucun coût à chaque interaction.
            st.download_button("Données corrigées (CSV)", partial(csv_bytes, validation["cleaned"]),
                               f"{base}_corrige.csv", "text/csv", icon=":material/table:", on_click="ignore")
            st.download_button("Lignes écartées (CSV)", lambda: csv_bytes(rejets_lisibles(validation["rejects"])),
                               f"{base}_lignes_ecartees.csv", "text/csv", icon=":material/playlist_remove:", on_click="ignore")
            st.download_button("Rapport qualité", lambda: rapport().encode("utf-8"), f"{base}_rapport_qualite.md",
                               "text/markdown", icon=":material/description:", on_click="ignore")
            st.download_button("Tout le projet (ZIP)",
                               lambda: archive_projet(source["contenu"], source["nom"], validation["cleaned"], validation["rejects"],
                                                      rapport(), validation["choix"], validation["log"], validation["plan"]["dictionary"]),
                               f"{base}_projet_{datetime.now(timezone.utc):%Y%m%d}.zip", "application/zip",
                               type="primary", icon=":material/folder_zip:", on_click="ignore")


def ecran_visualiser():
    """Écran de l'étape 4."""
    etat = st.session_state
    validation = etat.get("validation")
    st.title("Vérifier vos données en graphiques", anchor=False)
    if validation is None:
        st.info("Validez d'abord vos corrections à l'étape Corriger, même si vous ne changez rien.", icon=":material/info:")
        st.button("Aller à l'étape Corriger", type="primary", icon=":material/arrow_back:", on_click=aller, args=("Corriger",))
        return
    st.caption("Ces graphiques servent à contrôler que les données corrigées sont plausibles avant l'analyse métier. "
               f"Ils portent sur les {validation['resultat']['gardees']:,} lignes gardées.".replace(",", " "))
    roles = _roles(validation)
    dayfirst = {col: valeur == "jour" for col, valeur in validation["choix"].get("dates", {}).items()}
    data, ignorees = cached(prepare, validation["cleaned"], roles, dayfirst)
    graphiques = [(g, None) for g in graphiques_controle(data, roles, ignorees)]
    graphiques += [(g, i) for i, spec in enumerate(etat.graphiques_ajoutes)
                   if (g := _graphique_ajoute(data, roles, spec, ignorees)) is not None]
    if not graphiques:
        st.info("Aucun graphique de contrôle possible : indiquez au moins une catégorie, un nombre ou une date à l'étape Comprendre.")
    for debut in range(0, len(graphiques), 2):
        for colonne, (graphique, retirer) in zip(st.columns(2), graphiques[debut:debut + 2]):
            with colonne:
                _carte(graphique, retirer)
    _section_ajout(roles)
    _section_export(validation)
    st.button("Retour aux corrections", icon=":material/arrow_back:", on_click=aller, args=("Corriger",))
