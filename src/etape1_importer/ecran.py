"""Étape 1 (Importer) : choisir un CSV, voir qu'il est bien lu, ajuster la lecture si besoin.

Entrée : le fichier déposé par l'utilisateur. Sorties en session : `source` (nom, contenu,
empreinte) et `raw` (données lues). Aucune saisie obligatoire.
Changer de fichier ou d'options de lecture efface l'analyse en cours, avec un avertissement
si des choix avaient déjà été faits.
"""
import hashlib
from pathlib import Path

import streamlit as st

from src.config import LIGNES_APERCU
from src.core.lecture import DECIMALES, ENCODAGES, SEPARATEURS, lire_avec_identifiants, separateur_probablement_faux
from src.core.session import aller, reinitialiser_analyse
from src.core.texte import nombre_lisible, pour_affichage

EXEMPLE = Path(__file__).parents[1] / "assets" / "exemple.csv"
GROS_FICHIER = 100 * 1024 * 1024
ICONE = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'%3E"
         "%3Crect width='60' height='60' rx='16' fill='%23E3F2F2'/%3E%3Cg transform='translate(16 16)' fill='none' "
         "stroke='%230B6F71' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M16.3 3.5H8.2"
         "a2.3 2.3 0 0 0-2.3 2.3v16.4a2.3 2.3 0 0 0 2.3 2.3h11.6a2.3 2.3 0 0 0 2.3-2.3V9.3z'/%3E%3Cpath d='M16.3 3.5v5.8h5.9'/%3E"
         "%3Cpath d='M14 19.8v-7'/%3E%3Cpath d='M11 15.7l3-3 3 3'/%3E%3C/g%3E%3C/svg%3E")
# La zone de dépôt de Streamlit est en anglais : ses textes sont remplacés par du style (Streamlit 1.66).
STYLE_DEPOT = """<style>
.st-key-import_zone h1 { text-align: center; font-size: 1.75rem; font-weight: 600; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] {
  flex-direction: column; justify-content: center; align-items: center; gap: 14px; padding: 44px 24px; text-align: center;
  background: #FFFFFF; border: 2px dashed #A9D3D3; border-radius: 18px; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] > span { display: flex; justify-content: center; }
.st-key-w_exemple button { color: #0B6F71; text-decoration: underline; text-underline-offset: 3px; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"]::before {
  content: "Glissez un fichier CSV ici"; display: block; padding-top: 74px; font-weight: 600; font-size: 1.05rem;
  background: url("ICONE") no-repeat center top; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] button {
  background: #0B6F71; border-color: #0B6F71; color: #FFFFFF; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] button:hover { background: #095C5E; border-color: #095C5E; color: #FFFFFF; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] button span:has(> [data-testid="stIconMaterial"]) { display: none; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] button p { font-size: 0; }
.st-key-w_fichier [data-testid="stFileUploaderDropzone"] button p::after { content: "Choisir un fichier"; font-size: 0.9rem; font-weight: 600; }
.st-key-w_fichier [data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 0; }
.st-key-w_fichier [data-testid="stFileUploaderDropzoneInstructions"] span::after { content: "INSTRUCTIONS"; font-size: 0.8rem; }
</style>"""


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


def _nouveau_fichier(nom, contenu):
    empreinte = hashlib.sha256(contenu).hexdigest()
    etat = st.session_state
    if etat.get("source", {}).get("empreinte") == empreinte:
        return
    reinitialiser_analyse()
    etat.source = {"nom": nom, "contenu": contenu, "empreinte": empreinte, "taille": len(contenu)}
    charger()


def _charger_exemple():
    _nouveau_fichier(EXEMPLE.name, EXEMPLE.read_bytes())


def _zone_depot():
    """Titre et zone de dépôt, centrés ; textes de la zone en français."""
    maximum = st.get_option("server.maxUploadSize")
    st.html(STYLE_DEPOT.replace("ICONE", ICONE).replace(
        "INSTRUCTIONS", f"CSV · {maximum} Mo maximum · l\'original n\'est jamais modifié"))
    _, milieu, _ = st.columns([1, 1.6, 1])
    with milieu, st.container(key="import_zone"):
        st.title("Importer un fichier", anchor=False)
        fichier = st.file_uploader("Fichier CSV", type=["csv"], key="w_fichier", label_visibility="collapsed")
        with st.container(horizontal=True, horizontal_alignment="center"):
            st.button("Essayer avec un exemple", type="tertiary", key="w_exemple", on_click=_charger_exemple)
    return fichier


def _changer_lecture(option, cle_widget):
    etat = st.session_state
    if cle_widget not in etat:
        # Clic relayé juste après un changement d'étape : le widget est déjà effacé, on l'ignore.
        return
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
    fichier = _zone_depot()
    if fichier is not None:
        _nouveau_fichier(fichier.name, fichier.getvalue())
    source = etat.get("source")
    if source is None:
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
    if source["taille"] > GROS_FICHIER:
        st.info("Gros fichier : comptez jusqu'à 30 secondes par étape et environ 4 Go de mémoire. "
                "Gardez un seul onglet ouvert sur l'outil.", icon=":material/hourglass_top:")

    st.subheader("Aperçu de vos données", anchor=False)
    apercu = raw.head(LIGNES_APERCU)
    st.dataframe(pour_affichage(apercu), alt=f"Les {len(apercu)} premières lignes du fichier")
    st.caption(f"Les {nombre_lisible(len(apercu))} premières lignes, telles qu'elles sont dans le fichier.")
    if etat.get("ids_texte"):
        st.caption(f"Lues comme du texte pour garder les zéros au début (ex. 001) : {', '.join(map(str, etat.ids_texte))}.")
    _options_lecture(une_colonne)

    st.button("Étape suivante : comprendre mes données", type="primary", icon=":material/arrow_forward:",
              icon_position="right", on_click=aller, args=("Comprendre",), disabled=une_colonne)
