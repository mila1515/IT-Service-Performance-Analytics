"""Étape 1 (Importer) : choisir un CSV, voir qu'il est bien lu, ajuster la lecture si besoin.

Entrée : le fichier déposé par l'utilisateur. Sorties en session : `source` (nom, contenu,
empreinte) et `raw` (données lues). Aucune saisie obligatoire.
Changer de fichier ou d'options de lecture efface l'analyse en cours, avec un avertissement
si des choix avaient déjà été faits.
"""
import hashlib

import streamlit as st

from src.config import LIGNES_APERCU
from src.core.lecture import DECIMALES, ENCODAGES, SEPARATEURS, lire_avec_identifiants, separateur_probablement_faux
from src.core.session import aller, reinitialiser_analyse
from src.core.texte import nombre_lisible, pour_affichage


@st.cache_data(ttl=3600, max_entries=3, show_spinner="Lecture du fichier…")
def _lire(contenu, separateur, encodage, decimale):
    return lire_avec_identifiants(contenu, separateur, encodage, decimale)


def charger():
    """Lit la source avec les options courantes ; le dictionnaire est reconstruit par l'étape 2."""
    etat = st.session_state
    lecture = etat.lecture
    try:
        raw, identifiants = _lire(etat.source["contenu"], lecture["separateur"], lecture["encodage"], lecture["decimale"])
    except (ValueError, UnicodeError) as exc:
        etat.erreur_lecture = str(exc)
        return
    etat.pop("erreur_lecture", None)
    etat.raw, etat.ids_texte = raw, identifiants
    etat.pop("dictionary", None)


def _nouveau_fichier(fichier):
    contenu = fichier.getvalue()
    empreinte = hashlib.sha256(contenu).hexdigest()
    etat = st.session_state
    if etat.get("source", {}).get("empreinte") == empreinte:
        return
    reinitialiser_analyse()
    etat.source = {"nom": fichier.name, "contenu": contenu, "empreinte": empreinte, "taille": len(contenu)}
    charger()


def _changer_lecture(option, cle_widget):
    etat = st.session_state
    etat.lecture = {**etat.lecture, option: etat[cle_widget]}
    if reinitialiser_analyse():
        etat.avertissement = ("Les options de lecture ont changé : le fichier a été relu et vos choix ont été effacés. "
                              "Fixez ces options avant de commencer les corrections.")
    charger()


def _options_lecture(ouvert):
    lecture = st.session_state.lecture
    with st.expander("Le tableau ne ressemble pas à votre fichier ?", expanded=ouvert, icon=":material/tune:"):
        st.caption("Si toutes les valeurs sont collées dans une seule colonne, ou si les accents sont mal affichés, "
                   "essayez une autre option. Le fichier est relu aussitôt.")
        for option, libelle, choix in [("separateur", "Séparateur des colonnes", SEPARATEURS),
                                       ("encodage", "Encodage des caractères", ENCODAGES),
                                       ("decimale", "Séparateur des décimales", DECIMALES)]:
            cle = f"w_lecture_{option}"
            st.segmented_control(libelle, list(choix), format_func=choix.get, default=lecture[option], required=True,
                                 key=cle, on_change=_changer_lecture, args=(option, cle))


def ecran_importer():
    """Écran de l'étape 1."""
    etat = st.session_state
    st.title("Importer votre fichier", anchor=False)
    st.caption("Choisissez un fichier CSV. Votre fichier d'origine n'est jamais modifié : "
               "toutes les corrections se font sur une copie.")
    fichier = st.file_uploader("Fichier CSV", type=["csv"], key="w_fichier")
    if fichier is not None:
        _nouveau_fichier(fichier)
    source = etat.get("source")
    if source is None:
        st.info("Déposez un fichier pour commencer. Aucune autre information n'est demandée à cette étape.",
                icon=":material/upload_file:")
        return
    if fichier is None:
        st.caption(f"Fichier en cours : **{source['nom']}**. Déposez un autre fichier pour le remplacer.")
    if "avertissement" in etat:
        st.warning(etat.pop("avertissement"), icon=":material/warning:")
    if "erreur_lecture" in etat:
        st.error(f"Le fichier n'a pas pu être lu avec ces options : {etat.erreur_lecture}", icon=":material/error:")
        _options_lecture(True)
        return

    raw = etat.raw
    une_colonne = separateur_probablement_faux(raw)
    if une_colonne:
        st.warning("Tout le fichier tient dans une seule colonne : le séparateur ne correspond sans doute pas. "
                   "Changez-le ci-dessous.", title="Le tableau semble mal découpé", icon=":material/warning:")
    else:
        st.success(f"{nombre_lisible(len(raw))} lignes et {nombre_lisible(len(raw.columns))} colonnes.",
                   title="Fichier lu correctement", icon=":material/check_circle:")

    st.subheader("Aperçu de vos données", anchor=False)
    apercu = raw.head(LIGNES_APERCU)
    st.dataframe(pour_affichage(apercu), alt=f"Les {len(apercu)} premières lignes du fichier")
    st.caption(f"Les {nombre_lisible(len(apercu))} premières lignes, telles qu'elles sont dans le fichier.")
    if etat.get("ids_texte"):
        st.caption(f"Lues comme du texte pour garder les zéros au début (ex. 001) : {', '.join(map(str, etat.ids_texte))}.")
    _options_lecture(une_colonne)

    st.button("Étape suivante : comprendre mes données", type="primary", icon=":material/arrow_forward:",
              icon_position="right", on_click=aller, args=("Comprendre",), disabled=une_colonne)
