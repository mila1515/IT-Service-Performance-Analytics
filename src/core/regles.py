"""Contrôles qualité et traitements avec références aux enregistrements sources."""


import json
import re

import numpy as np
import pandas as pd

from src.core.dictionnaire import convert, normalize_missing

CHECKS = ["Obligatoire", "Unique", "Intervalle", "Catégories autorisées", "Format", "Ordre des dates"]

AUDIT_COLUMNS = ["ID", "Colonne", "Dimension", "Règle", "Seuil (%)", "Anomalies", "Lignes", "Taux (%)", "Statut", "Priorité"]


def validate_rule(rule, columns):
    if rule["column"] not in columns or rule["kind"] not in CHECKS + ["Clé composée unique"]:
        raise ValueError("Colonne ou contrôle inconnu.")
    if rule["priority"] not in ("P1", "P2", "P3") or not 0 <= rule["threshold"] <= 100:
        raise ValueError("Priorité ou seuil invalide.")
    kind = rule["kind"]
    if kind == "Clé composée unique":
        keys = rule.get("columns", [])
        if not keys or len(set(keys)) != len(keys) or any(c not in columns for c in keys):
            raise ValueError("La combinaison doit contenir des colonnes existantes et distinctes.")
    if kind == "Intervalle" and (not np.isfinite(rule["low"]) or not np.isfinite(rule["high"]) or rule["low"] > rule["high"]):
        raise ValueError("Intervalle invalide.")
    if kind == "Format":
        if len(rule["pattern"]) > 200:
            raise ValueError("Expression de format trop longue (200 caractères maximum).")
        re.compile(rule["pattern"])
    if kind == "Catégories autorisées" and not rule["values"]:
        raise ValueError("Précisez au moins une catégorie autorisée.")
    if kind == "Ordre des dates" and (rule["other"] not in columns or rule["other"] == rule["column"]):
        raise ValueError("Choisissez deux colonnes de dates différentes.")


def audit(data, dictionary, rules):
    reference = normalize_missing(data, dictionary)
    definitions = {d["Colonne"]: d for d in dictionary}
    checks = []
    for i, d in enumerate(dictionary):
        for key, kind in (("Obligatoire", "Obligatoire"), ("Unique", "Unique")):
            if d[key]:
                checks.append({"id": f"D-{i}-{kind}", "column": d["Colonne"], "kind": kind,
                               "priority": "P1" if d["Critique"] else "P2", "threshold": 0.})
        if d["Type attendu"] in ("Nombre", "Date"):
            checks.append({"id": f"D-{i}-type", "column": d["Colonne"], "kind": "Type",
                           "priority": "P1" if d["Critique"] else "P2", "threshold": 0.})
    checks += rules
    rows, details = [], []
    for rule in checks:
        col, kind = rule["column"], rule["kind"]
        values = reference[col]
        present = values.notna()
        dimension = "Conformité"
        if kind == "Obligatoire":
            bad, dimension = ~present, "Complétude"
        elif kind == "Unique":
            bad, dimension = values.duplicated(keep=False) & present, "Unicité"
        elif kind == "Clé composée unique":
            keys = rule["columns"]
            bad = reference[keys].notna().all(axis=1) & reference.duplicated(subset=keys, keep=False)
            dimension = "Unicité"
        elif kind == "Type":
            d = definitions[col]
            bad = present & convert(values, d["Type attendu"], d["Format date"]).isna()
        elif kind == "Intervalle":
            numbers = convert(values, "Nombre")
            bad = present & ~numbers.between(rule["low"], rule["high"])
        elif kind == "Catégories autorisées":
            bad = present & ~values.astype("string").isin(rule["values"])
        elif kind == "Format":
            bad = present & ~values.astype("string").str.fullmatch(rule["pattern"], na=False)
        else:
            other = rule["other"]
            left = convert(values, "Date", definitions[col]["Format date"])
            right = convert(reference[other], "Date", definitions[other]["Format date"])
            comparable = present & reference[other].notna()
            bad = comparable & (left.isna() | right.isna() | (left < right))
            dimension = "Cohérence"
        bad = bad.fillna(False)
        count = int(bad.sum())
        pct = count / len(reference) * 100 if len(reference) else 0.
        rows.append({"ID": rule["id"], "Colonne": col, "Dimension": dimension,
                     "Règle": kind + (f" ≥ {rule['other']}" if kind == "Ordre des dates" else " (" + " + ".join(rule["columns"]) + ")" if kind == "Clé composée unique" else ""),
                     "Seuil (%)": rule["threshold"], "Anomalies": count, "Lignes": len(reference),
                     "Taux (%)": round(pct, 2), "Statut": "Non évalué" if reference.empty else "Conforme" if pct <= rule["threshold"] else "Non conforme",
                     "Priorité": rule["priority"]})
        for index in reference.index[bad]:
            detail_value = json.dumps({c: str(data.loc[index, c]) for c in rule["columns"]}, ensure_ascii=False) if kind == "Clé composée unique" else str(data.loc[index, col])
            details.append({"Enregistrement source": int(index)+1, "ID règle": rule["id"],
                            "Colonne": col, "Valeur": detail_value, "Motif": kind})
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS), pd.DataFrame(details, columns=["Enregistrement source", "ID règle", "Colonne", "Valeur", "Motif"])


def compare_audits(before, before_details, after, after_details, kept_index):
    """Rejoue avant / après en séparant ce qui a été exclu de ce qui a été résolu.

    `kept_index` : index source des lignes conservées (le nettoyé garde l'index du brut).
    Une anomalie disparue parce que sa ligne a été écartée n'est pas une correction.
    """
    keys = ["ID", "Colonne", "Dimension", "Règle", "Seuil (%)", "Priorité"]
    comparison = before.merge(after, on=keys, suffixes=(" avant", " après"))
    kept = {int(i) + 1 for i in kept_index}

    def flagged(details, rule_id):
        return set(details.loc[details["ID règle"] == rule_id, "Enregistrement source"])

    excluded, resolved, new = [], [], []
    for rule_id in comparison["ID"]:
        b, a = flagged(before_details, rule_id), flagged(after_details, rule_id)
        excluded.append(len(b - kept))
        resolved.append(len((b & kept) - a))
        new.append(len(a - b))
    comparison["Écartées par exclusion de lignes"] = excluded
    comparison["Résolues sur lignes conservées"] = resolved
    comparison["Nouvelles anomalies"] = new
    return comparison


def recommendation(audit_after, row_count):
    if row_count == 0:
        return "NO-GO", "Aucune ligne exploitable."
    if audit_after.empty:
        return "À évaluer", "Aucune règle de qualité définie."
    failed = audit_after.loc[audit_after["Statut"] != "Conforme"]
    if (failed["Priorité"] == "P1").any():
        return "NO-GO", "Au moins un contrôle critique P1 échoue."
    if not failed.empty:
        return "GO avec réserves", "Des contrôles P2/P3 restent non conformes."
    return "GO", "Tous les contrôles définis sont conformes ; seuls ces contrôles ont été évalués."
