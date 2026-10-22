"""État de session Streamlit, commun aux écrans : mémoïsation des calculs, navigation et réinitialisations.

Seul module de `core/` qui dépend de Streamlit : le cache et l'état servent à toutes les étapes.
Clés du parcours simple : `source` (fichier importé), `lecture` (options), `raw`, `dictionary`,
`choix` (décisions de l'étape Corriger), `validation` (résultat validé), `graphiques_ajoutes`,
`notes`, `etape` (étape affichée). Les fonctions `invalidate_cleaning` et `reset_dashboard`
servent au mode expert.
"""
import json

import streamlit as st


MAX_ENTRIES = 12
ETAPES = ["Importer", "Comprendre", "Corriger", "Visualiser"]
# Effacées quand le fichier ou ses options de lecture changent ; le fichier et les options restent.
CLES_ANALYSE = ("raw", "ids_texte", "dictionary", "choix", "validation", "graphiques_ajoutes", "notes", "session_cache")
PREFIXES_WIDGETS_ANALYSE = ("w_choix_", "w_role_", "w_ajout_", "w_notes")


def cached(fn, data, *params):
    """`data` doit rester le même objet d'une interaction à l'autre (brut ou nettoyé en session).

    Les paramètres sont comparés par leur contenu JSON. Le résultat est partagé :
    l'appelant ne doit pas le modifier.
    """
    store = st.session_state.setdefault("session_cache", {})
    key = (fn.__module__, fn.__qualname__, id(data),
           json.dumps(params, sort_keys=True, default=str, ensure_ascii=False))
    if key not in store:
        while len(store) >= MAX_ENTRIES:
            store.pop(next(iter(store)))
        # La référence à `data` empêche la réutilisation de son id par un autre objet.
        store[key] = (data, fn(data, *params))
    return store[key][1]


def initialiser():
    """Valeurs par défaut du parcours simple, posées une seule fois par session."""
    etat = st.session_state
    etat.setdefault("lecture", {"separateur": ",", "encodage": "utf-8-sig", "decimale": "."})
    etat.setdefault("choix", {})
    etat.setdefault("graphiques_ajoutes", [])
    etat.setdefault("etape", ETAPES[0])


def travail_en_cours():
    """Vrai si l'utilisateur a déjà fait des choix, validé, modifié un rôle ou ajouté un graphique."""
    etat = st.session_state
    return bool(etat.get("choix") or etat.get("graphiques_ajoutes") or etat.get("roles_modifies") or "validation" in etat)


def reinitialiser_analyse():
    """Efface l'analyse en cours (pas le fichier). Retourne True si du travail a été perdu."""
    etat = st.session_state
    perdu = travail_en_cours()
    for cle in list(etat):
        if cle in CLES_ANALYSE or cle == "roles_modifies" or cle.startswith(PREFIXES_WIDGETS_ANALYSE):
            del etat[cle]
    initialiser()
    return perdu


def aller(etape):
    """Rappel de bouton : change l'étape affichée (avant que la barre d'étapes soit dessinée)."""
    st.session_state.etape = etape


def invalidate_cleaning():
    for key in ("cleaned", "preview", "rejects", "log", "config", "decision", "decision_reason"):
        st.session_state.pop(key, None)


def reset_dashboard(roles, dayfirst=None):
    """Nouveaux rôles ou format de date : les graphiques et filtres existants ne sont plus valides."""
    state = st.session_state
    state.viz_roles = roles
    if dayfirst is not None:
        state.viz_dayfirst = dayfirst
    state.viz_charts = []
    state.viz_filters = []
    state.viz_revision = state.get("viz_revision", 0) + 1
