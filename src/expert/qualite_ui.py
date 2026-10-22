"""Écrans de cadrage, dictionnaire, audit et comparaison."""


import re
import uuid

import pandas as pd
import streamlit as st

from src.core.dictionnaire import TYPES, records
from src.core.regles import CHECKS, audit, validate_rule
from src.core.roles import ROLES
from src.core.session import cached, invalidate_cleaning, reset_dashboard


def missing_marker_editor(diagnostic, key):
    suspects = diagnostic["suspects"]
    if suspects.empty:
        return
    with st.expander("Valeurs manquantes possibles : voir les nombres et les reconnaître", expanded=not diagnostic["normalized"].isna().any().any()):
        st.dataframe(suspects, hide_index=True)
        st.caption("Ces valeurs sont encore conservées. Appliquez seulement si elles signifient réellement un vide dans les colonnes indiquées. Le dictionnaire permet un choix plus fin par colonne.")
        tokens = suspects["Valeur à vérifier"].unique().tolist()
        if len(tokens) == 1:
            selected = tokens
            label = f"Reconnaître {tokens[0]} comme vide dans les colonnes du tableau"
        else:
            selected = st.multiselect("Marqueurs à reconnaître comme vides", tokens, key=f"{key}_tokens")
            label = "Reconnaître les marqueurs sélectionnés dans les colonnes du tableau"
        if st.button(label, key=f"{key}_apply"):
            if not selected:
                st.info("Sélectionnez au moins un marqueur.")
            else:
                state = st.session_state
                for definition in state.dictionary:
                    matches = suspects.loc[(suspects.Colonne == definition["Colonne"]) & suspects["Valeur à vérifier"].isin(selected), "Valeur à vérifier"].tolist()
                    if matches:
                        existing = definition["Marqueurs vides"].splitlines()
                        definition["Marqueurs vides"] = "\n".join(dict.fromkeys(existing + matches))
                state.pop("dictionary_editor", None)
                invalidate_cleaning()
                st.rerun()


def context():
    state = st.session_state
    st.caption("Ces notes sont facultatives. Complétez-les au fil de vos observations ; vous pouvez laisser ce qui n'est pas encore connu vide.")
    for key, label in [("project_name", "Nom du projet (facultatif)"),
                       ("expected_decision", "Décision métier à éclairer avec les résultats (facultatif)"),
                       ("source_description", "Description de la source (facultatif)")]:
        state[key] = st.text_input(label, value=state.get(key, ""), key=f"field_{key}")
    choices = ["À préciser", "Oui", "Non"]
    state.sensitive = st.selectbox("Présence de données sensibles", choices, index=choices.index(state.get("sensitive", "À préciser")), key="field_sensitive")
    for key, label in [("grain", "D'après les observations, que représente une ligne ? (facultatif)"),
                       ("period_description", "Période observée dans les données (facultatif)")]:
        state[key] = st.text_input(label, value=state.get(key, ""), key=f"field_{key}")
    for key, label in [("analysis_questions", "Questions à approfondir après exploration (facultatif)"),
                       ("kpi_definitions", "Indicateurs retenus au fil de l'analyse (facultatif)")]:
        state[key] = st.text_area(label, value=state.get(key, ""), key=f"field_{key}")


def dictionary_editor(raw):
    state = st.session_state
    st.subheader("Dictionnaire de données")
    st.caption("Définissez les types avant le nettoyage. Les marqueurs vides sont saisis un par ligne et restent propres à chaque colonne. Dates : format explicite, par exemple %d/%m/%Y %H:%M ; sinon ISO 8601.")
    with st.form("dictionary_form"):
        edited = st.data_editor(pd.DataFrame(state.dictionary), hide_index=True, disabled=["Colonne", "Type observé"],
                                column_config={"Type attendu": st.column_config.SelectboxColumn(options=TYPES, required=True),
                                               "Rôle": st.column_config.SelectboxColumn(options=ROLES, required=True)},
                                key="dictionary_editor", num_rows="fixed")
        if st.form_submit_button("Enregistrer le dictionnaire"):
            candidate = records(edited.fillna({c: "" for c in ["Définition", "Unité", "Marqueurs vides", "Format date"]}))
            if any(d["Type attendu"] not in TYPES or d["Rôle"] not in ROLES for d in candidate):
                st.error("Choisissez un type et un rôle valides pour chaque colonne.")
            else:
                state.dictionary = candidate
                invalidate_cleaning()
                reset_dashboard({d["Colonne"]: d["Rôle"] for d in candidate})
                st.success("Dictionnaire enregistré. Les traitements doivent être prévisualisés et validés de nouveau.")


def audit_editor(raw):
    state = st.session_state
    st.subheader("Diagnostic qualité avant nettoyage")
    st.caption("Les manquants tiennent compte des marqueurs définis dans le dictionnaire. Unicité : toutes les occurrences dupliquées renseignées sont signalées. Les autres contrôles ignorent les vides ; combinez-les avec « Obligatoire ». Taux calculé sur toutes les lignes.")
    with st.expander("Ajouter une règle métier"):
        kind = st.selectbox("Contrôle", CHECKS)
        with st.form("quality_rule_form"):
            col = st.selectbox("Colonne contrôlée", list(raw))
            priority = st.selectbox("Priorité", ["P1", "P2", "P3"], index=1)
            threshold = st.number_input("Pourcentage d'anomalies toléré", min_value=0., max_value=100., value=0.)
            rule = {"id": "Q-"+uuid.uuid4().hex[:8], "column": col, "kind": kind, "priority": priority, "threshold": threshold}
            if kind == "Intervalle":
                rule["low"] = st.number_input("Borne minimale", value=0.)
                rule["high"] = st.number_input("Borne maximale", value=100.)
            elif kind == "Catégories autorisées":
                rule["values"] = [v.strip() for v in st.text_area("Catégories autorisées (une par ligne)").splitlines() if v.strip()]
            elif kind == "Format":
                rule["pattern"] = st.text_input("Expression régulière du format", value="[0-9]{5}")
            elif kind == "Ordre des dates":
                rule["other"] = st.selectbox("Doit être supérieure ou égale à", list(raw))
            if st.form_submit_button("Ajouter la règle"):
                try:
                    validate_rule(rule, raw.columns)
                    state.quality_rules.append(rule)
                    invalidate_cleaning()
                    st.success("Règle ajoutée ; les traitements doivent être validés de nouveau.")
                except (ValueError, re.error) as exc:
                    st.error(str(exc))
    if state.quality_rules:
        labels = {r["id"]: f"{r['id']} · {r['column']} · {r['kind']}" for r in state.quality_rules}
        selected = st.selectbox("Règle à retirer", list(labels), format_func=labels.get)
        if st.button("Retirer la règle"):
            state.quality_rules = [r for r in state.quality_rules if r["id"] != selected]
            invalidate_cleaning()
            st.rerun()
        with st.expander("Définition complète des règles"):
            st.json(state.quality_rules)
    summary, details = cached(audit, raw, state.dictionary, state.quality_rules)
    if summary.empty:
        st.info("Aucune règle définie. Déclarez les champs obligatoires / uniques et types attendus dans le dictionnaire, ou ajoutez une règle.")
    else:
        st.dataframe(summary, hide_index=True)
        with st.expander("Enregistrements à investiguer"):
            st.dataframe(details, hide_index=True)
            st.caption("L'enregistrement source est le numéro de ligne de données à partir de 1, hors en-tête ; un champ CSV multiligne reste un seul enregistrement.")
        st.download_button("Exporter l'audit avant nettoyage", summary.to_csv(index=False).encode("utf-8-sig"), "audit_avant.csv", "text/csv")
