"""Étape 2 (Comprendre) : ce que contient le fichier, colonne par colonne, et les points à vérifier.

Entrées en session : `raw`, `dictionary`, `choix`, `regles`. Rien n'est modifié ici, sauf le type
d'une colonne si l'utilisateur le corrige (clic sur l'étiquette du type) et les règles facultatives
cochées sur les cartes (doit être remplie, valeurs uniques, entre deux bornes).
"""
import pandas as pd
import streamlit as st

from src.core.dessins import mini_repartition, periodes
from src.core.regles import regles_simples
from src.core.session import aller, cached
from src.core.texte import nombre_lisible, pluriel, pour_affichage
from src.etape2_comprendre.colonnes import resume_colonnes
from src.etape2_comprendre.diagnostic import diagnose
from src.etape2_comprendre.points import compter_espaces, detecter_points, dictionnaire_selon_choix, verifier_regles
from src.etape2_comprendre.repetitions import part_lisible, variations

COLONNES_LISTEES = 8

ROLES = {"Identifiant": "des identifiants", "Catégorie": "des catégories", "Mesure": "des nombres", "Date": "des dates"}


def diagnostic_courant():
    """Diagnostic mémorisé du brut avec le dictionnaire courant (codes « ? » comptés à part)."""
    etat = st.session_state
    return cached(diagnose, etat.raw, etat.dictionary, True)


def regles_actives():
    """Règles cochées sur les cartes de l'étape Comprendre."""
    return st.session_state.regles


def points_courants(choix=None):
    """Points à vérifier selon les données, les rôles, les choix (ceux de l'écran par défaut) et les règles cochées."""
    etat = st.session_state
    return cached(_detecter, etat.raw, etat.dictionary, etat.choix if choix is None else choix, etat.regles)


def _detecter(raw, dictionary, choix, regles):
    # Le diagnostic et les espaces ne dépendent pas des choix : ils restent mémorisés quand seuls les choix changent.
    return detecter_points(raw, dictionary, choix, cached(diagnose, raw, dictionary, True), regles_simples(regles),
                           cached(compter_espaces, raw))


def _verifier(raw, dictionary, choix, regles):
    # Les codes déjà reconnus comme manquants à l'étape Corriger comptent comme des cases vides.
    dico, _ = dictionnaire_selon_choix(dictionary, choix, cached(diagnose, raw, dictionary, True)["suspects"])
    return verifier_regles(raw, dico, regles_simples(regles))


def resultats_regles():
    """Lignes qui ne respectent pas chaque règle cochée (vide si aucune)."""
    etat = st.session_state
    regles = regles_actives()
    return cached(_verifier, etat.raw, etat.dictionary, etat.choix, regles) if regles else {}


def _changer_regle(colonne, type_, cle_widget, bornes=None):
    etat = st.session_state
    if cle_widget not in etat:
        # Clic relayé juste après un changement d'étape : le widget est déjà effacé, on l'ignore.
        return
    regle = dict(etat.regles.get(colonne, {}))
    if type_ == "bornes":
        regle["bornes"] = list(bornes) if etat[cle_widget] else None
    else:
        regle[type_] = etat[cle_widget]
    etat.regles = {**etat.regles, colonne: regle}


def _changer_borne(colonne, position, cle_widget):
    etat = st.session_state
    if cle_widget not in etat:
        # Clic relayé juste après un changement d'étape : le widget est déjà effacé, on l'ignore.
        return
    regle = dict(etat.regles.get(colonne, {}))
    bornes = list(regle.get("bornes") or [0., 0.])
    bornes[position] = float(etat[cle_widget])
    etat.regles = {**etat.regles, colonne: {**regle, "bornes": bornes}}


def _resultat_regle(controle, resultats):
    numeros = resultats.get(controle["id"], [])
    if not numeros:
        st.badge("Respectée par toutes les lignes", color="green", icon=":material/check:")
        return
    exemple = ", ".join(map(str, numeros[:5])) + (" …" if len(numeros) > 5 else "")
    _alerte(f"{pluriel(len(numeros), 'ligne ne respecte pas', 'lignes ne respectent pas')} "
            f"({'ligne' if len(numeros) == 1 else 'lignes'} {exemple})")


def _regles(fiche, index, resultats):
    """Volet « Règles (facultatif) » d'une carte, fermé par défaut."""
    colonne, role = fiche["colonne"], fiche["role"]
    regle = st.session_state.regles.get(colonne, {})
    with st.expander("Règles (facultatif)", expanded=any(regle.values()), icon=":material/rule:",
                     key=f"w_regle_{index}_volet"):
        types = [("remplie", "Doit être remplie")] + ([("unique", "Valeurs uniques")] if role == "Identifiant" else [])
        for type_, libelle in types:
            cle = f"w_regle_{index}_{type_}"
            st.checkbox(libelle, value=bool(regle.get(type_)), key=cle, on_change=_changer_regle, args=(colonne, type_, cle))
            if regle.get(type_):
                _resultat_regle(regles_simples({colonne: {type_: True}})[0], resultats)
        if role == "Mesure" and fiche.get("nombres"):
            cle = f"w_regle_{index}_bornes"
            defaut = (fiche["minimum"], fiche["maximum"])
            st.checkbox("Valeurs entre deux bornes", value=bool(regle.get("bornes")), key=cle,
                        on_change=_changer_regle, args=(colonne, "bornes", cle, defaut))
            if regle.get("bornes"):
                gauche, droite = st.columns(2)
                for colonne_ecran, position, libelle in ((gauche, 0, "Minimum"), (droite, 1, "Maximum")):
                    cle_borne = f"w_regle_{index}_borne_{position}"
                    colonne_ecran.number_input(libelle, value=float(regle["bornes"][position]), key=cle_borne,
                                               on_change=_changer_borne, args=(colonne, position, cle_borne))
                _resultat_regle(regles_simples({colonne: {"bornes": regle["bornes"]}})[0], resultats)


def _changer_role(colonne, cle_widget):
    etat = st.session_state
    if cle_widget not in etat:
        # Clic relayé juste après un changement d'étape : le widget est déjà effacé, on l'ignore.
        return
    role = next(r for r, libelle in ROLES.items() if libelle == etat[cle_widget])
    etat.dictionary = [dict(d, **({"Rôle": role} if d["Colonne"] == colonne else {})) for d in etat.dictionary]
    etat.roles_modifies = True
    # Les corrections validées reposaient sur les anciens rôles.
    etat.pop("validation", None)


def _alerte(texte):
    st.badge(texte, color="orange", icon=":material/warning:")


def _liste(colonnes):
    reste = len(colonnes) - COLONNES_LISTEES
    return ", ".join(colonnes[:COLONNES_LISTEES]) + (f" et {pluriel(reste, 'autre')}" if reste > 0 else "")


def _repetitions(fiche, index):
    """Volet « Pourquoi … se répète ? » : calculé seulement quand il est ouvert."""
    colonne = fiche["colonne"]
    volet = st.expander(f"Pourquoi « {colonne} » se répète ?", key=f"w_repet_{index}", on_change="rerun",
                        icon=":material/difference:")
    if not volet.open:
        return
    with volet:
        resultat = cached(variations, diagnostic_courant()["normalized"], colonne)
        if resultat["changent"]:
            st.markdown(f"Ce qui change entre les lignes d'une même valeur ({pluriel(resultat['lignes'], 'ligne')} "
                        f"concernées) :\n" + "\n".join(
                f"- {c} : change dans {part_lisible(p)} des groupes" for c, p in resultat["changent"][:COLONNES_LISTEES]))
            if len(resultat["changent"]) > COLONNES_LISTEES:
                reste = len(resultat["changent"]) - COLONNES_LISTEES
                st.caption(f"Et {pluriel(reste, 'autre colonne qui change', 'autres colonnes qui changent')}.")
            if resultat["identiques"]:
                st.caption(f"Identiques dans tous les groupes : {_liste(resultat['identiques'])}.")
        else:
            st.info("Les lignes répétées sont des copies identiques : voir la carte « Des lignes identiques » "
                    "à l'étape Corriger.", icon=":material/content_copy:")
        total = resultat["exemple_total"]
        affichees = len(resultat["exemple_lignes"])
        st.markdown(f"**Exemple : « {resultat['exemple']} »**, {pluriel(total, 'ligne')}"
                    + (f" ({affichees} premières)" if affichees < total else ""))
        st.dataframe(pour_affichage(resultat["exemple_lignes"]), alt=f"Lignes de « {resultat['exemple']} »")
        st.caption("Une valeur répétée n'est pas forcément une erreur : vérifiez ce que représente une ligne de votre fichier.")


def _type(fiche, index):
    """Étiquette du type ; un clic ouvre le choix pour le corriger."""
    cle = f"w_role_{index}"
    with st.popover(fiche["libelle"], icon=":material/edit:", help="Changer le type de cette colonne"):
        st.radio("Cette colonne contient", list(ROLES.values()), index=list(ROLES).index(fiche["role"]), key=cle,
                 on_change=_changer_role, args=(fiche["colonne"], cle))


def _carte(fiche, index, resultats):
    with st.container(border=True, height="stretch", key=f"carte_colonne_{index}"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{fiche['colonne']}**")
            _type(fiche, index)
        st.caption(fiche["phrase"])
        st.markdown(f"Remplies : **{nombre_lisible(fiche['remplies'])}** sur {nombre_lisible(fiche['total'])} · "
                    f"Valeurs différentes : **{nombre_lisible(fiche['distinctes'])}**")
        role = fiche["role"]
        if role == "Identifiant" and fiche["exemple_repete"]:
            valeur, fois = fiche["exemple_repete"]
            _alerte(f"« {valeur} » apparaît {fois} fois" if fiche["repetees"] == 1
                    else f"{nombre_lisible(fiche['repetees'])} valeurs apparaissent plusieurs fois")
            _repetitions(fiche, index)
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
        _regles(fiche, index, resultats)


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
    resultats = resultats_regles()
    for debut in range(0, len(fiches), 2):
        colonnes = st.columns(2)
        for colonne, (index, fiche) in zip(colonnes, enumerate(fiches[debut:debut + 2], start=debut)):
            with colonne:
                _carte(fiche, index, resultats)

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
