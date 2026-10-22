"""Écran de nettoyage : observation, choix ciblés, prévisualisation, validation."""
from copy import deepcopy
from datetime import datetime, timezone

import streamlit as st

from src.analysis import duplicate_rows, numeric_columns
from src.diagnostics import diagnose
from src.quality import audit, pipeline, recommendation
from src.quality_ui import invalidate_cleaning, missing_marker_editor
from src.session_cache import cached


def cleaning_screen(raw, next_step):
    state = st.session_state
    diagnostic = cached(diagnose, raw, state.dictionary)
    columns = diagnostic["columns"]
    affected = columns.loc[columns["Vides après conversion"] > 0]
    reference = diagnostic["normalized"]
    st.subheader("Observer avant de nettoyer")
    a, b, c = st.columns(3)
    a.metric("Cellules vides détectées", int(reference.isna().sum().sum()))
    b.metric("Lignes avec au moins un vide", int(reference.isna().any(axis=1).sum()))
    c.metric("Doublons stricts en excès", cached(duplicate_rows, raw))
    if not affected.empty:
        st.dataframe(affected, hide_index=True)
        st.caption("Moyenne et médiane : valeurs renseignées avant les exclusions choisies. Elles seront recalculées sur les lignes conservées. Les échecs de conversion restent bloqués par défaut.")
    elif diagnostic["suspects"].empty:
        st.success("Aucune valeur manquante détectée. Aucun choix de remplacement à faire.")
    else:
        st.info("Aucune cellule vide, mais des marqueurs peuvent représenter des données manquantes. Vérifiez le tableau ci-dessous avant de choisir un traitement.")
    missing_marker_editor(diagnostic, "clean_markers")
    hints = diagnostic["numeric_hints"]
    if not hints.empty:
        st.info(f"Colonnes surtout numériques mais traitées comme du texte : {', '.join(map(str, hints.Colonne))}. Moyenne et médiane ne sont proposées qu'après avoir déclaré le type « Nombre » et le rôle « Mesure » à l'étape 2 ; les valeurs non convertibles seront alors bloquées jusqu'à votre choix.")

    previous = state.get("config", {})
    st.subheader("Choisir les corrections utiles")
    st.caption("Conserver est le choix par défaut. Seules les colonnes avec des vides ou des échecs de conversion sont proposées.")
    with st.form("cleaning"):
        rules = {col: "Conserver" for col in raw}
        for i, col in enumerate(raw.columns):
            row = columns.loc[columns.Colonne == col].iloc[0]
            if not row["Vides après conversion"]:
                continue
            d = next(d for d in state.dictionary if d["Colonne"] == col)
            choices = ["Conserver", "Supprimer les lignes"]
            if d["Rôle"] == "Mesure" and col in numeric_columns(diagnostic["prepared"]):
                choices += ["Moyenne", "Médiane"]
            elif d["Rôle"] == "Catégorie" and d["Type attendu"] in ("Conserver", "Texte"):
                choices += ["Inconnu"]
            default = previous.get("rules", {}).get(col, "Conserver")
            count = int(row["Vides après conversion"])
            pct = count / len(raw)*100 if len(raw) else 0.
            rules[col] = st.selectbox(f"{col} — {count} vides après conversion ({pct:.2f} %)", choices,
                                      index=choices.index(default) if default in choices else 0, key=f"rule_{i}")
        with st.expander("Autres corrections et traçabilité (facultatif)"):
            trim = st.checkbox("Normaliser les espaces de début / fin", value=previous.get("trim", False))
            dedup = st.checkbox("Supprimer les lignes strictement identiques", value=previous.get("deduplicate", False))
            policies = ["Bloquer", "Mettre en rejet", "Convertir en vide"]
            conversion_policy = previous.get("conversion_policy", "Bloquer")
            if columns["Conversions impossibles"].sum():
                conversion_policy = st.selectbox("Si une conversion de type échoue", policies, index=policies.index(conversion_policy))
            audit_before, _ = cached(audit, raw, state.dictionary, state.quality_rules)
            ids = audit_before.ID.tolist()
            labels = {r["ID"]: f"{r['ID']} · {r['Colonne']} · {r['Règle']}" for r in audit_before.to_dict("records")}
            reject_ids = []
            if ids:
                reject_ids = st.multiselect("Mettre en rejet les lignes qui échouent à ces règles", ids,
                                            default=[r for r in previous.get("reject_rule_ids", []) if r in ids], format_func=labels.get)
            owner = st.text_input("Responsable du traitement (facultatif)", value=previous.get("owner", ""))
            justification = st.text_area("Note sur les traitements (facultatif)", value=previous.get("justification", ""))
            st.caption("Chaque action est enregistrée automatiquement dans le journal. Les lignes supprimées restent disponibles dans les rejets.")
        preview = st.form_submit_button("Prévisualiser les traitements", type="primary")
    if preview:
        state.pop("preview", None)
        try:
            justification = justification.strip() or "Plan sélectionné dans l'interface ; choix et actions consignés automatiquement."
            candidate, rejects, log = pipeline(raw, state.dictionary, state.quality_rules, rules,
                            trim=trim, deduplicate=dedup, conversion_policy=conversion_policy,
                            reject_rule_ids=reject_ids, justification=justification, owner=owner)
            config = {"rules": rules, "trim": trim, "deduplicate": dedup, "conversion_policy": conversion_policy,
                      "reject_rule_ids": reject_ids, "justification": justification, "owner": owner}
            state.preview = candidate, rejects, log, config
        except ValueError as exc:
            st.error(str(exc))
    if "preview" in state:
        candidate, rejects, log, config = state.preview
        st.subheader("Vérifier le résultat proposé")
        a, b, c = st.columns(3)
        a.metric("Lignes conservées", len(candidate), delta=len(candidate)-len(raw))
        b.metric("Vides restants", int(candidate.isna().sum().sum()))
        c.metric("Lignes mises en rejet", len(rejects))
        st.dataframe(candidate.head(20), hide_index=True)
        with st.expander("Détail des traitements, contrôles et rejets"):
            st.write("Traitements", config)
            st.dataframe(rejects, hide_index=True)
            preview_audit, _ = cached(audit, candidate, state.dictionary, state.quality_rules)
            st.dataframe(preview_audit, hide_index=True)
            decision, reason = recommendation(preview_audit, len(candidate))
            st.info(f"{decision} — {reason}")
        if st.button("Valider cette prévisualisation", type="primary"):
            state.cleaned, state.rejects, state.log, state.config = candidate, rejects, log, config
            state.pop("decision", None)
            state.pop("decision_reason", None)
            state.cleaning_versions.append({"cleaned": candidate.to_csv(index=False), "rejects": rejects.to_csv(index=False),
                "recipe": deepcopy({"date_utc": datetime.now(timezone.utc).isoformat(), "config": config,
                        "dictionnaire": state.dictionary, "regles_qualite": state.quality_rules, "journal": log})})
            state.pending_step = next_step
            st.rerun()
    if "cleaned" in state and st.button("Revenir aux données brutes"):
        invalidate_cleaning()
        st.rerun()
