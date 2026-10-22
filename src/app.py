"""Analyse simple : auditer et préparer la qualité d'un fichier CSV avant l'analyse métier.

Lancer depuis la racine : python -m streamlit run src/app.py
Parcours en 4 étapes, une par dossier : etape1_importer → etape2_comprendre → etape3_corriger
→ etape4_visualiser. Ce fichier ne contient que la navigation ; l'ancienne interface complète
reste disponible à côté (src/expert/app_expert.py).
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.session import ETAPES, aller, initialiser
from src.etape1_importer.ecran import ecran_importer
from src.etape2_comprendre.colonnes import dictionnaire_propose
from src.etape2_comprendre.ecran import ecran_comprendre
from src.etape3_corriger.ecran import ecran_corriger
from src.etape4_visualiser.ecran import ecran_visualiser

ECRANS = {"Importer": ecran_importer, "Comprendre": ecran_comprendre, "Corriger": ecran_corriger, "Visualiser": ecran_visualiser}
ICONES = {"Importer": ":material/upload_file:", "Comprendre": ":material/visibility:",
          "Corriger": ":material/build:", "Visualiser": ":material/bar_chart:"}

st.set_page_config(page_title="Analyse simple", page_icon=":material/fact_check:", layout="wide",
                   initial_sidebar_state="collapsed")
initialiser()
etat = st.session_state

with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
    st.markdown("**Analyse simple** · audit qualité avant l'analyse métier")
    st.segmented_control("Étapes", ETAPES, key="etape", required=True, label_visibility="collapsed",
                         format_func=lambda e: f"{ICONES[e]} {ETAPES.index(e) + 1} · {e}")

if etat.etape != "Importer" and etat.get("raw") is None:
    st.info("Importez d'abord un fichier CSV.", icon=":material/upload_file:")
    st.button("Aller à l'import", type="primary", icon=":material/arrow_back:", on_click=aller, args=("Importer",))
    st.stop()
if etat.get("raw") is not None and "dictionary" not in etat:
    etat.dictionary = dictionnaire_propose(etat.raw)

ECRANS[etat.etape]()
