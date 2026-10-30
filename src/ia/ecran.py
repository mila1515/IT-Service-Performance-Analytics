"""Onglet « Assistant IA » : explique le fichier, conseille des corrections et propose des analyses.

Entrées en session : `raw`, `dictionary`, `choix`. Sortie : `ia` (réponses retenues, reprises par les cartes de l'étape 3
et par le rapport). L'IA n'est appelée qu'au clic et ne modifie aucune donnée. L'onglet reste utilisable sans clé.
"""
import re

import streamlit as st

from src.core.session import cached
from src.etape2_comprendre.colonnes import resume_colonnes
from src.etape2_comprendre.ecran import diagnostic_courant, points_courants
from src.ia import client
from src.ia.conseils import lire_comprendre, lire_pistes, lire_suggestions, messages
from src.ia.resume import construire_resume

VUES = {"comprendre": ("Comprendre mon fichier", ":material/visibility:"),
        "corriger": ("Conseils de correction", ":material/build:"),
        "analyser": ("Pistes d'analyse", ":material/insights:")}


def sans_mise_en_forme(texte):
    """Le texte de l'IA ou du fichier s'affiche tel quel : ni lien, ni image, ni mise en forme."""
    return re.sub(r"([\\`*_{}\[\]()#+!|~$<>:])", r"\\\1", str(texte))


def afficher_suggestion(type_, cle, options):
    """Étape 3 : la suggestion de l'IA sous une carte, s'il y en a une. Elle ne coche rien."""
    for s in (st.session_state.get("ia") or {}).get("corriger") or []:
        if s["type"] == type_ and s["cle"] == cle and s["choix"] in options:
            st.caption(f":material/lightbulb: **Suggestion IA : {sans_mise_en_forme(options[s['choix']])}** — "
                       f"{sans_mise_en_forme(s['raison'])}")
            return


def _interroger(type_, resume, references, points, noms):
    reponse = client.demander(messages(type_, resume))
    if type_ == "comprendre":
        return lire_comprendre(reponse, noms)
    if type_ == "corriger":
        return lire_suggestions(reponse, references, points, noms)
    return lire_pistes(reponse, noms)


def _contenu(vue, ia):
    """La réponse de la vue choisie, déjà reçue : changer de vue n'appelle pas l'IA."""
    if vue not in ia:
        st.caption("Pas encore de réponse pour cette partie.")
    elif vue == "comprendre":
        st.markdown(sans_mise_en_forme(ia[vue]["resume"]))
        st.markdown("\n".join(f"- {sans_mise_en_forme(p)}" for p in ia[vue]["a_regarder"]))
    elif vue == "corriger":
        st.caption("À appliquer vous-même à l'étape Corriger : chaque conseil y apparaît aussi sous sa carte.")
        if not ia[vue]:
            st.info("L'IA n'a donné aucun conseil exploitable. Vous pouvez réessayer.", icon=":material/info:")
        for s in ia[vue]:
            st.markdown(f"**{sans_mise_en_forme(s['probleme'])}** → {sans_mise_en_forme(s['options'][s['choix']])}  \n"
                        f"{sans_mise_en_forme(s['raison'])}")
    else:
        st.caption("À lancer vous-même à l'étape Analyser : les chiffres y sont calculés par l'outil.")
        if not ia[vue]:
            st.info("L'IA n'a proposé aucune piste exploitable. Vous pouvez réessayer.", icon=":material/info:")
        for p in ia[vue]:
            colonnes = f" ({', '.join(sans_mise_en_forme(c) for c in p['colonnes'])})" if p["colonnes"] else ""
            st.markdown(f"**{sans_mise_en_forme(p['question'])}**  \n{p['analyse']}{colonnes} — "
                        f"{sans_mise_en_forme(p['pourquoi'])}")


def ecran_ia():
    """Écran de l'onglet Assistant IA."""
    etat = st.session_state
    st.title("Assistant IA", anchor=False)
    st.caption("L'IA conseille à partir d'un résumé, vous décidez. Elle peut se tromper et ne modifie aucune donnée.")
    if not client.cle_api():
        st.info("Ajoutez la ligne `OPENAI_API_KEY=votre_clé` dans un fichier `.env` à la racine du projet, puis relancez "
                "l'outil. Les autres étapes fonctionnent sans clé.", title="Clé API à configurer", icon=":material/key:")
        return

    points = points_courants()
    diagnostic = diagnostic_courant()
    fiches = cached(resume_colonnes, etat.raw, etat.dictionary)
    masquer = st.checkbox("Masquer les noms de colonnes", key="w_ia_masquer",
                          help="Envoie « Colonne 1, Colonne 2… ». Les conseils seront moins précis ; les vrais noms "
                               "sont rétablis sur votre poste.")
    resume, references, noms = construire_resume(etat.raw, etat.dictionary, points, diagnostic, fiches, masquer)
    with st.expander("Voir exactement ce qui sera envoyé à OpenAI"):
        st.caption("Jamais les lignes du fichier ni les valeurs d'exemple. Chaque clic consomme un peu de votre crédit.")
        st.json(resume, expanded=2)

    vue = st.segmented_control("Partie affichée", list(VUES), default="comprendre", required=True, key="w_ia_vue",
                               format_func=lambda v: f"{VUES[v][1]} {VUES[v][0]}", label_visibility="collapsed")
    with st.container(border=True, key="carte_ia"):
        with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
            st.subheader(VUES[vue][0], anchor=False)
            demande = st.button("Redemander à l'IA" if vue in (etat.get("ia") or {}) else "Demander à l'IA", type="primary",
                                icon=":material/smart_toy:", key="w_ia_demander", disabled=vue == "corriger" and not references)
        if demande:
            try:
                with st.spinner("L'IA réfléchit…"):
                    etat.ia = {**etat.get("ia", {}), vue: _interroger(vue, resume, references, points, noms)}
            except client.ErreurIA as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                st.rerun()  # le bouton affiche aussitôt « Redemander à l'IA »
        _contenu(vue, etat.get("ia") or {})
