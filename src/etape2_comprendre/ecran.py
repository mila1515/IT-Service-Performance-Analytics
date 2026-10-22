"""Étape 2 (Comprendre) : ce que contient le fichier, colonne par colonne, et les points à vérifier.

Entrées en session : `raw`, `dictionary`, `choix`. Rien n'est modifié ici, sauf le rôle d'une
colonne si l'utilisateur le corrige (« Cette colonne contient… »).
"""
import pandas as pd
import streamlit as st

from src.core.dessins import mini_repartition, periodes
from src.core.session import aller, cached
from src.core.texte import nombre_lisible, pluriel
from src.etape2_comprendre.colonnes import resume_colonnes
from src.etape2_comprendre.diagnostic import diagnose
from src.etape2_comprendre.points import detecter_points

ROLES = {"Identifiant": "des identifiants", "Catégorie": "des catégories", "Mesure": "des nombres", "Date": "des dates"}


def diagnostic_courant():
    """Diagnostic mémorisé du brut avec le dictionnaire courant (codes « ? » comptés à part)."""
    etat = st.session_state
    return cached(diagnose, etat.raw, etat.dictionary, True)


def points_courants():
    """Points à vérifier selon les données, les rôles et les choix déjà faits."""
    etat = st.session_state
    return cached(_detecter, etat.raw, etat.dictionary, etat.choix)


def _detecter(raw, dictionary, choix):
    # Le diagnostic ne dépend pas des choix : il reste mémorisé quand seuls les choix changent.
    return detecter_points(raw, dictionary, choix, cached(diagnose, raw, dictionary, True))


def _changer_role(colonne, cle_widget):
    etat = st.session_state
    role = next(r for r, libelle in ROLES.items() if libelle == etat[cle_widget])
    etat.dictionary = [dict(d, **({"Rôle": role} if d["Colonne"] == colonne else {})) for d in etat.dictionary]
    etat.roles_modifies = True
    # Les corrections validées reposaient sur les anciens rôles.
    etat.pop("validation", None)


def _alerte(texte):
    st.badge(texte, color="orange", icon=":material/warning:")


def _carte(fiche, index):
    with st.container(border=True, height="stretch"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{fiche['colonne']}**")
            st.badge(fiche["libelle"], color="gray")
        st.caption(fiche["phrase"])
        st.markdown(f"Remplies : **{nombre_lisible(fiche['remplies'])}** sur {nombre_lisible(fiche['total'])} · "
                    f"Valeurs différentes : **{nombre_lisible(fiche['distinctes'])}**")
        role = fiche["role"]
        if role == "Identifiant" and fiche["exemple_repete"]:
            valeur, fois = fiche["exemple_repete"]
            _alerte(f"« {valeur} » apparaît {fois} fois" if fiche["repetees"] == 1
                    else f"{nombre_lisible(fiche['repetees'])} valeurs apparaissent plusieurs fois")
        elif role == "Catégorie" and fiche["frequences"]:
            st.altair_chart(mini_repartition(fiche["frequences"]), alt=f"Valeurs les plus fréquentes de {fiche['colonne']}")
            if fiche["autres"]:
                st.caption(f"Et {nombre_lisible(fiche['autres'])} lignes avec d'autres valeurs.")
        elif role == "Mesure":
            if fiche["nombres"]:
                st.markdown(f"Minimum **{nombre_lisible(fiche['minimum'])}** · Médiane **{nombre_lisible(fiche['mediane'])}** · "
                            f"Moyenne **{nombre_lisible(fiche['moyenne'])}** · Maximum **{nombre_lisible(fiche['maximum'])}**")
                st.caption(f"Calculé sur les {nombre_lisible(fiche['nombres'])} valeurs qui sont des nombres.")
            if fiche["non_numeriques"]:
                _alerte(f"{pluriel(fiche['non_numeriques'], 'valeur')} qui ne {'sont' if fiche['non_numeriques'] > 1 else 'est'} pas un nombre")
        elif role == "Date" and fiche.get("periodes"):
            st.markdown(f"Du **{fiche['debut']:%d/%m/%Y}** au **{fiche['fin']:%d/%m/%Y}**")
            if len(fiche["periodes"]) > 1:
                donnees = pd.DataFrame(fiche["periodes"], columns=["Période", "Lignes"])
                st.altair_chart(periodes(donnees).properties(height=140), alt=f"Lignes par {fiche['unite']} pour {fiche['colonne']}")
            if fiche["illisibles"]:
                _alerte(f"{pluriel(fiche['illisibles'], 'date illisible', 'dates illisibles')}")
        if fiche["remplies"] < fiche["total"]:
            st.caption(f"{pluriel(fiche['total'] - fiche['remplies'], 'case vide', 'cases vides')}.")
        cle = f"w_role_{index}"
        st.selectbox("Cette colonne contient", list(ROLES.values()), index=list(ROLES).index(role), key=cle,
                     on_change=_changer_role, args=(fiche["colonne"], cle))


def ecran_comprendre():
    """Écran de l'étape 2."""
    etat = st.session_state
    st.title("Comprendre vos données", anchor=False)
    st.caption("Voici ce que contient votre fichier, colonne par colonne. Rien n'a encore été modifié.")
    points = points_courants()
    nb_points = sum(len(p["lignes"]) for p in points)
    with st.container(horizontal=True):
        st.metric("Lignes", nombre_lisible(len(etat.raw)), border=True)
        st.metric("Colonnes", nombre_lisible(len(etat.raw.columns)), border=True)
        st.metric("Points à vérifier", nombre_lisible(nb_points), border=True)

    st.subheader(f"Vos {pluriel(len(etat.raw.columns), 'colonne')}", anchor=False)
    dayfirst = {cle: valeur == "jour" for cle, valeur in etat.choix.get("dates", {}).items()}
    fiches = cached(resume_colonnes, etat.raw, etat.dictionary, dayfirst)
    for debut in range(0, len(fiches), 2):
        colonnes = st.columns(2)
        for colonne, (index, fiche) in zip(colonnes, enumerate(fiches[debut:debut + 2], start=debut)):
            with colonne:
                _carte(fiche, index)

    st.subheader("À vérifier avant d'analyser", anchor=False)
    if points:
        st.markdown("\n".join(f"- {ligne['texte']}" for point in points for ligne in point["lignes"]))
    else:
        st.success("Aucun point à vérifier n'a été repéré.", icon=":material/check_circle:")
    st.info("Une valeur manquante n'est pas toujours une case vide : un code comme « ? », « NA » ou « inconnu » "
            "peut aussi vouloir dire « pas d'information ».", title="Bon réflexe", icon=":material/lightbulb:")

    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Retour à l'import", icon=":material/arrow_back:", on_click=aller, args=("Importer",))
        libelle = f"Étape suivante : corriger {pluriel(nb_points, 'point')}" if nb_points else "Étape suivante : valider les données"
        st.button(libelle, type="primary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=aller, args=("Corriger",))
