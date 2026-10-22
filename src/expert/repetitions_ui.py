"""Exploration facultative des répétitions pour tout domaine métier."""


import json
import uuid

import streamlit as st

from src.core.dictionnaire import normalize_missing, records
from src.core.session import cached, invalidate_cleaning
from src.expert.repetitions import inspect_repetitions


def repetition_editor(raw):
    state = st.session_state
    st.subheader("Comprendre les clés répétées")
    st.caption("Choisissez les colonnes qui identifient une entité, puis éventuellement celles qui distinguent ses lignes ou événements. Aucun métier n'est présélectionné. Ce diagnostic ne supprime, ne fusionne et ne rejette aucune ligne.")
    config = state.get("repetition_config", {})
    keys = st.multiselect("Clé de regroupement (une ou plusieurs colonnes)", list(raw), default=config.get("keys", []), key="repeat_keys_input")
    available = [c for c in raw if c not in keys]
    detail = st.multiselect("Colonnes distinguant les lignes / événements (facultatif)", available,
                            default=[c for c in config.get("detail", []) if c in available], key="repeat_detail_input")
    candidates = [c for c in available if c not in detail]
    compared = st.multiselect("Champs à comparer pour une même clé de ligne", candidates,
                              default=[c for c in config.get("compared", candidates) if c in candidates], key="repeat_compared_input")
    if st.button("Analyser les répétitions"):
        if not keys:
            st.warning("Sélectionnez au moins une colonne de regroupement.")
        else:
            state.repetition_config = {"keys": keys, "detail": detail, "compared": compared}
    config = state.get("repetition_config")
    if not config:
        st.info("Sans clé choisie, les contrôles existants restent inchangés.")
        return
    if config != {"keys": keys, "detail": detail, "compared": compared}:
        st.info("Les résultats ci-dessous correspondent aux derniers paramètres analysés. Cliquez sur « Analyser les répétitions » pour appliquer vos nouveaux choix.")
    reference = cached(normalize_missing, raw, state.dictionary)
    result = inspect_repetitions(reference, config["keys"], config["detail"], config["compared"], source=raw)
    st.write("Paramètres analysés", config)
    st.caption("Comparaison sur les valeurs importées avec les marqueurs vides du dictionnaire. Aucune conversion de type ni harmonisation de texte n'est appliquée ici. Les clés incomplètes sont séparées des répétitions.")
    st.write(f"{len(result['summary'])} groupes répétés ; {len(result['incomplete'])} enregistrements avec une clé de regroupement incomplète.")
    if result["incomplete"]:
        with st.expander("Clés de regroupement incomplètes"):
            st.write("Enregistrements sources", result["incomplete"])
            st.dataframe(raw.loc[[i-1 for i in result["incomplete"]]], hide_index=True)
    if not result["summary"].empty:
        st.dataframe(result["summary"], hide_index=True)
        selected = st.selectbox("Groupe à examiner", result["summary"]["Groupe"].tolist(), key="repeat_group_input")
        members = result["membership"].loc[result["membership"]["Groupe"] == selected, "Enregistrement source"].tolist()
        st.write("Enregistrements sources", members)
        st.dataframe(raw.loc[[i-1 for i in members]], hide_index=True)
        st.dataframe(result["differences"].loc[result["differences"]["Groupe"] == selected], hide_index=True)
    st.caption("Des détails distincts ne prouvent pas la validité métier, et des lignes identiques ne prouvent pas une erreur. Les différences peuvent aussi représenter des versions successives.")
    export = {"configuration": config, "groupes": records(result["summary"]), "enregistrements": records(result["membership"]),
              "differences": records(result["differences"]), "cles_incompletes": result["incomplete"]}
    st.download_button("Exporter le diagnostic des répétitions", json.dumps(export, ensure_ascii=False, indent=2), "repetitions.json", "application/json")
    with st.expander("Déclarer une règle d'unicité composée (facultatif)"):
        leaf = config["keys"] + config["detail"]
        st.write("Combinaison contrôlée", leaf)
        confirmed = st.checkbox("Je confirme que cette combinaison doit être unique dans mon jeu de données", key=f"repeat_unique_confirm_{tuple(leaf)}")
        priority = st.selectbox("Priorité de l'unicité composée", ["P1", "P2", "P3"], index=1)
        if st.button("Ajouter le contrôle d'unicité composée"):
            if not confirmed:
                st.warning("Confirmez la règle métier avant de l'ajouter.")
            elif any(r.get("kind") == "Clé composée unique" and set(r.get("columns", [])) == set(leaf) for r in state.quality_rules):
                st.info("Cette combinaison est déjà contrôlée.")
            else:
                state.quality_rules.append({"id": "K-"+uuid.uuid4().hex[:8], "column": leaf[0], "columns": leaf,
                                            "kind": "Clé composée unique", "priority": priority, "threshold": 0.})
                invalidate_cleaning()
                st.success("Contrôle ajouté. Les lignes ne sont pas supprimées ; revalidez le nettoyage pour rejouer les contrôles.")
