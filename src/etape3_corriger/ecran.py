"""Étape 3 (Corriger) : une carte par problème, un choix en un clic, le résultat recalculé en direct.

Entrées en session : `raw`, `dictionary`, `choix`. Sortie : `validation` (choix retenus, plan,
données corrigées, lignes écartées, journal, résumé) au clic sur « Valider ».
Par défaut, chaque choix laisse les données inchangées.
"""
import hashlib

import streamlit as st

from src.core.regles import regles_simples
from src.core.session import aller, cached
from src.core.texte import nombre_lisible, pour_affichage
from src.etape2_comprendre.ecran import diagnostic_courant, points_courants, regles_actives, resultats_regles
from src.etape2_comprendre.points import exemples
from src.etape3_corriger.correction import (choix_complets, executer, phrases_journal, plan_nettoyage, regles_signalees,
                                            resume_resultat)


def _cle_widget(type_, cle):
    # Clé stable même si l'ordre des lignes change (les cases vides dépendent des autres choix).
    return f"w_choix_{type_}_{hashlib.md5(str(cle).encode()).hexdigest()[:10]}"


def _enregistrer(type_, cle, cle_widget):
    etat = st.session_state
    etat.choix = {**etat.choix, type_: {**etat.choix.get(type_, {}), cle: etat[cle_widget]}}


def _corriger(raw, plan):
    cleaned, rejects, log = executer(raw, plan)
    return {"cleaned": cleaned, "rejects": rejects, "log": log, "resultat": resume_resultat(raw, plan, cleaned, rejects)}


def _choix_et_plan():
    """Points, choix complets, diagnostic et plan de nettoyage, d'après les choix en session."""
    etat = st.session_state
    points = points_courants()
    complets = choix_complets(points, etat.choix)
    diagnostic = diagnostic_courant()
    return points, complets, diagnostic, plan_nettoyage(etat.dictionary, complets, diagnostic["suspects"],
                                                        regles_simples(regles_actives()))


def _valider():
    # Relu au clic : sur un gros fichier, l'affichage peut ne pas avoir fini d'intégrer le dernier choix.
    etat = st.session_state
    _, complets, _, plan = _choix_et_plan()
    try:
        corrige = cached(_corriger, etat.raw, plan)
    except ValueError:
        return
    resultats = resultats_regles()
    etat.validation = {"choix": complets, "plan": plan, "regles_verifiees": resultats,
                       "regles_signalees": regles_signalees(resultats, complets), **corrige}
    aller("Visualiser")


def _ligne(point, ligne, choisi, diagnostic):
    options = {cle: libelle for cle, libelle, _ in ligne["options"]}
    cle_widget = _cle_widget(point["type"], ligne["cle"])
    st.markdown(f"**{ligne['texte']}**")
    st.segmented_control(ligne["texte"], list(options), format_func=options.get, default=choisi,
                         required=True, key=cle_widget, label_visibility="collapsed",
                         on_change=_enregistrer, args=(point["type"], ligne["cle"], cle_widget))
    volet = st.expander("Voir les lignes concernées", key=f"{cle_widget}_lignes", on_change="rerun")
    if volet.open:
        with volet:
            lignes = exemples(st.session_state.raw, diagnostic, point["type"], ligne["cle"], numeros=ligne.get("numeros"))
            st.dataframe(pour_affichage(lignes, numeroter=False), alt=f"Exemples de lignes concernées : {ligne['texte']}")


def _resultat(corrige, signalees):
    resultat = corrige["resultat"]
    with st.container(border=True, key="carte_resultat"):
        st.subheader("Résultat de vos choix", anchor=False)
        with st.container(horizontal=True):
            st.metric("Lignes gardées", f"{nombre_lisible(resultat['gardees'])} / {nombre_lisible(resultat['total'])}")
            st.metric("Lignes écartées", nombre_lisible(resultat["ecartees"]))
            st.metric("Cases vides", f"{nombre_lisible(resultat['vides_avant'])} → {nombre_lisible(resultat['vides_apres'])}",
                      help="Avant → après vos choix, en comptant les codes reconnus comme valeurs manquantes.")
            for moyenne in resultat["moyennes"][:1]:
                avant = nombre_lisible(moyenne["avant"]) if moyenne["avant"] is not None else "—"
                apres = nombre_lisible(moyenne["apres"]) if moyenne["apres"] is not None else "—"
                st.metric(f"Moyenne de {moyenne['colonne']}", f"{avant} → {apres}",
                          help=f"Avant : {nombre_lisible(moyenne['n_avant'])} valeurs · après : {nombre_lisible(moyenne['n_apres'])} valeurs.")
        if resultat["ecartees"]:
            motifs = "\n".join(f"- {motif} : {nombre_lisible(n)}" for motif, n in resultat["motifs"])
            st.warning("Les lignes écartées ne sont pas effacées : elles sont mises de côté dans un fichier à part, avec "
                       "la raison. Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé.\n\n" + motifs,
                       title="Écarter n'est pas corriger", icon=":material/info:")
        st.markdown("**Noté automatiquement dans le journal**")
        st.markdown("\n".join(f"- {phrase}" for phrase in phrases_journal(corrige["log"], signalees)))


def ecran_corriger():
    """Écran de l'étape 3."""
    etat = st.session_state
    points, complets, diagnostic, plan = _choix_et_plan()
    total = sum(len(p["lignes"]) for p in points)
    st.title("Corriger les points à vérifier" if total else "Aucun point à vérifier", anchor=False)
    st.caption("Choisissez pour chaque point. Par défaut, rien n'est changé.")
    for point in points:
        with st.container(border=True, key=f"carte_point_{point['type']}"):
            st.subheader(point["titre"], anchor=False, help=point["pourquoi"])
            for ligne in point["lignes"]:
                _ligne(point, ligne, complets[point["type"]][ligne["cle"]], diagnostic)

    try:
        corrige = cached(_corriger, etat.raw, plan)
    except ValueError as exc:
        st.error(f"Ces choix ne peuvent pas être appliqués : {exc}", icon=":material/error:")
        return
    _resultat(corrige, regles_signalees(resultats_regles(), complets))
    validation = etat.get("validation")
    if validation and validation["choix"] != complets:
        st.info("Vos choix ont changé depuis la dernière validation. Validez de nouveau pour mettre à jour les graphiques.",
                icon=":material/sync:")

    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Retour à la compréhension", icon=":material/arrow_back:", on_click=aller, args=("Comprendre",))
        st.button("Valider et voir les graphiques", type="primary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=_valider)
