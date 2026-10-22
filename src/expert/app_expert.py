"""Mode expert (gardé à côté) : ancienne interface complète en 6 étapes.

Lancer depuis la racine : python -m streamlit run src/expert/app_expert.py
"""
import hashlib
import io
import json
import sys
from copy import deepcopy
from functools import partial
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.core.dictionnaire import initial_dictionary, normalize_missing, records
from src.core.regles import audit, compare_audits, recommendation
from src.core.session import cached
from src.core.statistiques import duplicate_rows, numeric_columns, profile, statistics
from src.etape2_comprendre.diagnostic import diagnose
from src.expert.dashboard import dashboard
from src.expert.nettoyage_ui import cleaning_screen
from src.expert.qualite_ui import (
    audit_editor,
    context,
    dictionary_editor,
    missing_marker_editor,
)
from src.expert.rapport_projet import project_archive
from src.expert.repetitions import inspect_repetitions
from src.expert.repetitions_ui import repetition_editor

st.set_page_config(page_title="Analyse guidée", page_icon="📊", layout="wide")
st.title("Analyse guidée")
st.caption("Comprendre vos données, choisir les traitements et vérifier leurs effets.")


def navigate(target):
    st.session_state.workflow_step = target


def session_has_work():
    state = st.session_state
    return bool(state.get("cleaning_versions") or state.get("quality_rules") or state.get("viz_charts")
                or "preview" in state or "repetition_config" in state
                or state.get("dictionary") != state.get("dictionary_initial"))


@st.cache_data(ttl=3600, max_entries=3, show_spinner=False)
def read_csv(payload, separator, encoding, decimal, text_columns):
    return pd.read_csv(io.BytesIO(payload), sep=separator, encoding=encoding, decimal=decimal,
                       dtype={c: "string" for c in text_columns}, keep_default_na=False, na_values=[""])


def non_measures():
    """Colonnes déclarées identifiant ou date : exclues des statistiques de mesures."""
    return [d["Colonne"] for d in st.session_state.dictionary if d["Rôle"] in ("Identifiant", "Date")]


def checks(data):
    """Audit mémorisé : rejoué seulement si les données, le dictionnaire ou les règles changent."""
    return cached(audit, data, st.session_state.dictionary, st.session_state.quality_rules)


def repetition_report(raw, dictionary, config):
    return inspect_repetitions(normalize_missing(raw, dictionary), config["keys"], config["detail"], config["compared"], source=raw)


def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def explore(data, key):
    diagnostic = cached(diagnose, data, st.session_state.dictionary)
    excluded = non_measures()
    duplicates = cached(duplicate_rows, data)
    reference = diagnostic["normalized"]
    a, b, c = st.columns(3)
    a.metric("Lignes", len(data))
    b.metric("Colonnes", len(data.columns))
    c.metric("Lignes strictement identiques en excès", duplicates)
    st.dataframe(data.head(20), hide_index=True)
    with st.expander("Échantillon aléatoire reproductible"):
        st.dataframe(data.sample(n=min(10, len(data)), random_state=42), hide_index=True)
    st.subheader("Ce qu'il faut observer")
    missing = diagnostic["columns"].loc[diagnostic["columns"]["Vides détectés"] > 0]
    if missing.empty:
        st.success("Aucune cellule vide détectée.")
    else:
        st.write(f"**{int(reference.isna().sum().sum())} cellules vides** dans **{len(missing)} colonnes**, concernant **{int(reference.isna().any(axis=1).sum())} lignes**.")
        st.dataframe(missing[["Colonne", "Vides détectés", "Vides (%)"]], hide_index=True)
    if not diagnostic["suspects"].empty:
        st.info(f"{int(diagnostic['suspects'].Occurrences.sum())} valeurs particulières (?, NA…) sont à vérifier ; elles ne sont pas remplacées automatiquement.")
        missing_marker_editor(diagnostic, key + "_markers")
    hints = diagnostic["numeric_hints"]
    if not hints.empty:
        st.info("Ces colonnes contiennent surtout des nombres, mais aussi des valeurs non numériques. Elles restent traitées comme du texte tant que vous ne déclarez pas le type « Nombre » (et le rôle « Mesure » s'il s'agit d'une mesure) dans « Adapter les types et les marqueurs vides ».")
        st.dataframe(hints, hide_index=True)
    if duplicates:
        st.write(f"**{duplicates} lignes strictement identiques en excès.** Vérifiez leur sens avant de les retirer.")
    with st.expander("Toutes les colonnes : types et valeurs distinctes"):
        st.dataframe(cached(profile, reference))
    st.subheader("Statistiques descriptives")
    stats = cached(statistics, data, excluded)
    if not stats.empty:
        st.dataframe(stats)
        st.caption("Variance et écart-type d'échantillon (n − 1). Les valeurs manquantes sont exclues des calculs.")
    skipped = [c for c in numeric_columns(data) if c in excluded]
    if skipped:
        st.caption(f"Colonnes numériques exclues des statistiques car déclarées identifiant ou date : {', '.join(map(str, skipped))}. Le rôle se corrige dans « Adapter les types et les marqueurs vides ».")
    col = st.selectbox("Explorer une colonne", data.columns, key=key)
    if col in numeric_columns(data) and col not in excluded:
        values = data[col].replace([float("inf"), -float("inf")], pd.NA).dropna()
        if not values.empty:
            bins = pd.cut(values, bins=20, duplicates="drop").value_counts(sort=False)
            bins.index = bins.index.astype(str)
            st.bar_chart(bins)
            q1, q3 = values.quantile([.25, .75])
            outliers = ((values < q1 - 1.5 * (q3-q1)) | (values > q3 + 1.5 * (q3-q1))).sum()
            st.info(f"{outliers} valeurs hors des bornes de Tukey (1,5 × IQR). Elles sont conservées.")
    else:
        counts = data[col].value_counts(dropna=False).head(20)
        st.dataframe(counts.rename("Effectif"))


with st.sidebar:
    st.header("Source")
    upload = st.file_uploader("Importer un CSV", type=["csv"], key="import_upload")
    with st.expander("Options de lecture du CSV"):
        separator = st.selectbox("Séparateur", [",", ";", "\t", "|"], format_func=lambda x: "Tabulation" if x == "\t" else x, key="import_separator")
        encoding = st.selectbox("Encodage", ["utf-8-sig", "cp1252"], key="import_encoding")
        decimal = st.selectbox("Séparateur décimal", [".", ","], key="import_decimal")
        st.caption("Modifier une option relit le fichier et réinitialise la session : dictionnaire, règles, nettoyages validés et dashboard.")
    st.caption("Les fichiers sources ne sont jamais écrasés. La session est conservée en mémoire.")

if upload is None:
    st.info("Importez un CSV pour commencer. Connexions aux bases et import Excel : extensions à venir.")
    st.stop()

payload = upload.getvalue()
try:
    header = pd.read_csv(io.BytesIO(payload), sep=separator, encoding=encoding, nrows=0).columns.tolist()
    with st.sidebar:
        with st.expander("Préserver les identifiants et codes"):
            text_columns = st.multiselect("Colonnes à lire comme texte", header, key="import_text_columns")
            st.caption("Choisissez les identifiants et codes pour préserver leurs zéros initiaux. Ce choix relit le fichier et réinitialise la session.")
    source_id = hashlib.sha256(payload + repr((separator, encoding, decimal, text_columns)).encode()).hexdigest()
    # Le brut reste le même objet en session : les calculs mémorisés s'y rattachent.
    if st.session_state.get("source_id") == source_id and "raw" in st.session_state:
        raw = st.session_state.raw
    else:
        raw = read_csv(payload, separator, encoding, decimal, tuple(text_columns))
    if raw.empty or len(raw.columns) == 0:
        st.warning("Le fichier ne contient aucune ligne exploitable.")
        st.stop()
except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
    st.error(f"Lecture impossible : {exc}")
    st.stop()

payload_sha = hashlib.sha256(payload).hexdigest()
if st.session_state.get("source_id") != source_id:
    # Même fichier relu avec d'autres options : le travail effacé est signalé.
    lost_work = st.session_state.get("import_payload_sha") == payload_sha and session_has_work()
    for key in list(st.session_state):
        if not key.startswith("import_"):
            del st.session_state[key]
    st.session_state.source_id = source_id
    st.session_state.reset_notice = lost_work
st.session_state.import_payload_sha = payload_sha
st.session_state.raw = raw

if "dictionary_initial" not in st.session_state:
    st.session_state.dictionary_initial = records(initial_dictionary(raw))
    st.session_state.dictionary = deepcopy(st.session_state.dictionary_initial)
st.session_state.setdefault("quality_rules", [])
st.session_state.setdefault("cleaning_versions", [])

steps = ["1 · Découverte du CSV", "2 · Exploration brute", "3 · Nettoyage", "4 · Comparaison",
         "5 · Analyse et visualisation", "6 · Synthèse et export"]
if "pending_step" in st.session_state:
    st.session_state.workflow_step = st.session_state.pop("pending_step")
step = st.sidebar.radio("Parcours", steps, key="workflow_step")
cleaned = st.session_state.get("cleaned")
if st.session_state.pop("reset_notice", False):
    st.warning("Les options de lecture ont changé : le fichier a été relu et la session réinitialisée (dictionnaire, règles, nettoyages validés, dashboard). Exportez l'archive du projet avant de modifier ces options.")

if step == steps[0]:
    st.subheader("Découvrir le fichier")
    st.write(f"**{upload.name}**")
    a, b = st.columns(2)
    a.metric("Lignes", len(raw))
    b.metric("Colonnes", len(raw.columns))
    st.caption("Voici les premières lignes, telles qu'importées. Faites défiler le tableau horizontalement pour voir les autres colonnes.")
    st.dataframe(raw.head(20), hide_index=True)
    numeric_ids = [d["Colonne"] for d in st.session_state.dictionary
                   if d["Rôle"] == "Identifiant" and d["Colonne"] in numeric_columns(raw)]
    if numeric_ids:
        st.info(f"Colonnes proposées comme identifiants mais lues comme nombres : {', '.join(map(str, numeric_ids))}. D'éventuels zéros initiaux ne sont pas affichés. Pour les conserver, sélectionnez-les dans « Préserver les identifiants et codes » (barre latérale), de préférence avant de commencer l'analyse.")
    st.info("Vous pouvez commencer sans connaître le rôle de chaque colonne, ce que représente une ligne, la période ou les indicateurs. L'étape « Exploration brute » sert à les découvrir.")
    st.button("Explorer les données", on_click=navigate, args=(steps[1],), type="primary")
elif step == steps[1]:
    explore(raw, "raw_column")
    with st.expander("Adapter les types et les marqueurs vides"):
        dictionary_editor(raw)
    with st.expander("Contrôles métier avancés"):
        audit_editor(raw)
    with st.expander("Examiner les clés répétées"):
        repetition_editor(raw)
    st.button("Continuer vers le nettoyage", on_click=navigate, args=(steps[2],), type="primary")
elif step == steps[2]:
    cleaning_screen(raw, steps[3])

else:
    if cleaned is None:
        st.info("Prévisualisez puis validez les traitements à l'étape 3, même si vous conservez les données telles quelles.")
        st.stop()
    if step == steps[3]:
        st.subheader("Avant / après")
        # Le brut est compté avec les mêmes marqueurs vides que le nettoyé.
        raw_missing = cached(normalize_missing, raw, st.session_state.dictionary)
        st.dataframe(pd.DataFrame({"Brut": [len(raw), int(raw_missing.isna().sum().sum()), cached(duplicate_rows, raw)],
                                  "Nettoyé": [len(cleaned), int(cleaned.isna().sum().sum()), cached(duplicate_rows, cleaned)]},
                                 index=["Lignes", "Cellules manquantes (marqueurs reconnus inclus)", "Doublons exacts en excès"]))
        st.caption("Une conversion de type impossible traitée en « Convertir en vide » ajoute des cellules manquantes dans le nettoyé.")
        st.dataframe(cached(statistics, raw, non_measures()).add_suffix(" · brut").join(cached(statistics, cleaned, non_measures()).add_suffix(" · nettoyé"), how="outer"))
        with st.expander("Journal des traitements"):
            st.write(st.session_state.get("log", []))
        st.caption(f"{len(st.session_state.cleaning_versions)} versions de nettoyage validées pendant cette session, incluses dans l'archive du projet.")
        st.subheader("Règles de qualité rejouées avant / après")
        before, before_details = checks(raw)
        after, details = checks(cleaned)
        comparison = compare_audits(before, before_details, after, details, cleaned.index)
        if comparison.empty:
            st.info("Aucune règle de qualité définie : rien ne permet de dire que les données sont fiables. Déclarez des champs obligatoires ou uniques dans le dictionnaire, ou ajoutez une règle à l'étape 2.")
        else:
            st.dataframe(comparison, hide_index=True)
            excluded = int(comparison["Écartées par exclusion de lignes"].sum())
            if excluded:
                st.warning(f"{excluded} anomalies ont disparu parce que leurs lignes ont été écartées (rejets) : ce n'est pas une correction des données.")
            st.caption("« Conforme » signifie seulement que le taux d'anomalies respecte le seuil des règles définies ; cela ne certifie pas l'exactitude métier. Pour l'unicité, écarter une occurrence résout aussi celle qui reste.")
            with st.expander("Enregistrements encore en anomalie après nettoyage"):
                st.dataframe(details, hide_index=True)
        st.write(f"**{len(st.session_state.rejects)} lignes mises en rejet**, conservées avec leur motif.")
        with st.expander("Examiner les rejets"):
            st.dataframe(st.session_state.rejects, hide_index=True)
        st.download_button("Exporter les rejets", partial(csv_bytes, st.session_state.rejects), "rejets.csv", "text/csv", on_click="ignore")
        st.download_button("Exporter les contrôles avant / après", comparison.to_csv(index=False).encode("utf-8-sig"), "controles.csv", "text/csv")
        st.button("Continuer vers les graphiques", on_click=navigate, args=(steps[4],), type="primary")
    elif step == steps[4]:
        if cleaned.empty:
            st.warning("Tous les enregistrements ont été supprimés. Revoyez les traitements.")
            st.stop()
        audit_after, _ = checks(cleaned)
        suggested, reason = recommendation(audit_after, len(cleaned))
        st.info(f"Évaluation des règles : {suggested} — {reason} Les graphiques ne certifient pas l'exactitude métier des données.")
        with st.expander("Explorer les données nettoyées et leurs statistiques"):
            explore(cleaned, "clean_column")
            nums = [c for c in numeric_columns(cleaned) if c not in non_measures()]
            if len(nums) >= 2:
                st.subheader("Corrélations numériques")
                st.dataframe(cleaned[nums].corr())
                st.caption("Une corrélation ne démontre pas une causalité. Vérifiez le sens métier et les effectifs.")
        dashboard(cleaned)
        st.button("Passer à la synthèse", on_click=navigate, args=(steps[5],))
    else:
        st.subheader("Documenter vos conclusions")
        with st.expander("Compléter le contexte et les observations (facultatif)"):
            context()
        st.session_state.conclusions = st.text_area("Constats, limites et recommandations", value=st.session_state.get("conclusions", ""), key="conclusions_input")
        before, before_details = checks(raw)
        after, after_details = checks(cleaned)
        suggested, reason = recommendation(after, len(cleaned))
        with st.expander("Décision formelle et réserves (facultatif)"):
            st.info(f"Évaluation des règles : {suggested} — {reason}")
            decisions = ["À évaluer", "GO", "GO avec réserves", "NO-GO"]
            st.session_state.decision = st.selectbox("Décision de l'utilisateur", decisions, index=decisions.index(st.session_state.get("decision", "À évaluer")), key="decision_input")
            st.session_state.decision_reason = st.text_area("Justification de la décision et réserves", value=st.session_state.get("decision_reason", ""), key="decision_reason_input")
            if st.session_state.decision != "À évaluer" and not st.session_state.decision_reason.strip():
                st.warning("La décision restera à évaluer dans le rapport tant que sa justification est vide.")
        # Fichiers générés au clic seulement : aucun coût à chaque interaction.
        st.download_button("Télécharger les données nettoyées", partial(csv_bytes, cleaned), "donnees_nettoyees.csv", "text/csv", on_click="ignore")
        report = {"source": upload.name, "objectif": st.session_state.get("objective", ""),
                  "granularite": st.session_state.get("grain", ""), "configuration": st.session_state.get("config", {}),
                  "historique": st.session_state.get("log", []), "conclusions": st.session_state.get("conclusions", ""),
                  "dashboard": {"version": 1, "roles": st.session_state.get("viz_roles", {}),
                                "dayfirst": st.session_state.get("viz_dayfirst", False),
                                "filters": st.session_state.get("viz_filters", []),
                                "charts": st.session_state.get("viz_charts", [])}}
        report.update({"cadrage": {k: st.session_state.get(k, "") for k in ["project_name", "expected_decision", "source_description", "period_description", "sensitive"]},
                       "dictionnaire": st.session_state.dictionary, "regles_qualite": st.session_state.quality_rules,
                       "questions_metier": st.session_state.get("analysis_questions", ""),
                       "definition_indicateurs": st.session_state.get("kpi_definitions", ""),
                       "audit_avant": records(before), "audit_apres": records(after),
                       "comparaison_controles": records(compare_audits(before, before_details, after, after_details, cleaned.index)),
                       "lignes": {"brut": len(raw), "nettoye": len(cleaned), "rejets": len(st.session_state.rejects)},
                       "statistiques_avant": records(cached(statistics, raw, non_measures()).reset_index()),
                       "statistiques_apres": records(cached(statistics, cleaned, non_measures()).reset_index()),
                       "evaluation_regles": {"resultat": suggested, "motif": reason},
                       "decision": st.session_state.decision if st.session_state.decision_reason.strip() else "À évaluer",
                       "justification_decision": st.session_state.decision_reason,
                       "empreinte_source_sha256": hashlib.sha256(payload).hexdigest()})
        report["import"] = {"separator": separator, "encoding": encoding, "decimal": decimal, "text_columns": text_columns}
        if "repetition_config" in st.session_state:
            cfg = st.session_state.repetition_config
            repetition_result = cached(repetition_report, raw, st.session_state.dictionary, cfg)
            report["repetitions"] = {"configuration": cfg, "groupes": records(repetition_result["summary"]),
                                     "enregistrements": records(repetition_result["membership"]),
                                     "differences": records(repetition_result["differences"]),
                                     "cles_incompletes": repetition_result["incomplete"]}
        st.download_button("Télécharger le rapport de traitement", json.dumps(report, ensure_ascii=False, indent=2), "rapport_analyse.json", "application/json")
        st.download_button("Télécharger les rejets", partial(csv_bytes, st.session_state.rejects), "rejets.csv", "text/csv", on_click="ignore")
        st.download_button("Télécharger l'archive du projet", partial(project_archive, payload, cleaned, st.session_state.rejects, report, list(st.session_state.cleaning_versions)), "projet_analyse.zip", "application/zip", on_click="ignore")
        st.caption("L'archive conserve le brut, les versions nettoyées, les rejets, les recettes, les résultats et la configuration du dashboard. Elle peut contenir des données sensibles. La restauration automatique d'une session complète reste à ajouter.")
