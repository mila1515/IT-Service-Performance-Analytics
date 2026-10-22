"""Contrôles qualité et traitements avec références aux enregistrements sources."""
from datetime import datetime, timezone
import json
import re

import numpy as np
import pandas as pd

from src.analysis import clean
from src.visualization import infer_roles

TYPES = ["Conserver", "Texte", "Nombre", "Date"]
CHECKS = ["Obligatoire", "Unique", "Intervalle", "Catégories autorisées", "Format", "Ordre des dates"]
AUDIT_COLUMNS = ["ID", "Colonne", "Dimension", "Règle", "Seuil (%)", "Anomalies", "Lignes", "Taux (%)", "Statut", "Priorité"]


def initial_dictionary(data):
    roles = infer_roles(data)
    return pd.DataFrame([{"Colonne": col, "Définition": "", "Type observé": str(data[col].dtype),
                          "Type attendu": "Conserver", "Rôle": roles[col], "Unité": "",
                          "Obligatoire": False, "Unique": False, "Critique": False,
                          "Marqueurs vides": "", "Format date": ""} for col in data])


def normalize_missing(data, dictionary):
    result = data.copy(deep=True)
    for d in dictionary:
        col = d["Colonne"]
        markers = [v.strip() for v in d["Marqueurs vides"].splitlines() if v.strip()]
        # Les cellules composées d'espaces sont vides ; les autres marqueurs sont explicites.
        # Test sur les valeurs distinctes : même résultat, coût réduit sur les gros fichiers.
        uniques = pd.Series(result[col].dropna().unique(), dtype=object)
        text = uniques.astype("string").str.strip()
        blanks = uniques[(text.eq("") | text.isin(markers)).fillna(False).to_numpy()]
        if len(blanks):
            result[col] = result[col].mask(result[col].isin(blanks.tolist()))
    return result


def convert(series, target, date_format=""):
    if target == "Nombre":
        return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    if target == "Date":
        return pd.to_datetime(series, format=date_format or "ISO8601", errors="coerce", utc=True).dt.tz_convert(None)
    if target == "Texte":
        return series.astype("string")
    return series.copy()


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


def pipeline(raw, dictionary, quality_rules, missing_rules, *, trim=False, deduplicate=False,
             conversion_policy="Bloquer", reject_rule_ids=None, justification="", owner=""):
    if conversion_policy not in ("Bloquer", "Mettre en rejet", "Convertir en vide"):
        raise ValueError("Politique de conversion inconnue.")
    work = normalize_missing(raw, dictionary)
    log, reasons = [], {}
    now = datetime.now(timezone.utc).isoformat()

    def record(action, col, count):
        if count:
            log.append({"Date UTC": now, "Colonne": col, "Action": action,
                        "Cellules / lignes": int(count), "Justification": justification, "Responsable": owner})

    def reject(index, reason):
        for idx in index:
            reasons.setdefault(idx, []).append(reason)

    if trim:
        for col in work.select_dtypes(include=["object", "string"]):
            previous = work[col].copy()
            work[col] = work[col].str.strip()
            record("Espaces de début / fin supprimés", col, (previous.notna() & previous.ne(work[col])).sum())
    for d in dictionary:
        col, target = d["Colonne"], d["Type attendu"]
        record("Marqueurs vides normalisés", col, (raw[col].notna() & work[col].isna()).sum())
        converted = convert(work[col], target, d["Format date"])
        failed = work[col].notna() & converted.isna()
        if failed.any():
            if conversion_policy == "Bloquer":
                raise ValueError(f"{col} : {int(failed.sum())} conversions impossibles. Corrigez le type/format ou choisissez explicitement leur traitement.")
            if conversion_policy == "Mettre en rejet":
                reject(work.index[failed], f"Conversion impossible : {col} → {target}")
            record(f"Conversions impossibles : {conversion_policy}", col, failed.sum())
        if target != "Conserver":
            record(f"Conversion en {target}", col, work[col].notna().sum())
        work[col] = converted
    # Les rejets de règles sont identifiés avant imputation, pour conserver le motif initial.
    if reject_rule_ids:
        _, anomalies = audit(raw, dictionary, quality_rules)
        for row in anomalies.to_dict("records"):
            if row["ID règle"] in reject_rule_ids:
                reject([row["Enregistrement source"]-1], f"{row['ID règle']} : {row['Motif']}")
    for col, action in missing_rules.items():
        if action == "Supprimer les lignes":
            reject(work.index[work[col].isna()], f"Valeur manquante : {col}")
    # Les lignes mises en rejet ne participent pas aux calculs de remplacement.
    reference = work.drop(index=list(reasons))
    cleaned, base_log = clean(reference, missing_rules)
    for entry in base_log:
        record(entry["Action"], entry["Colonne"], entry["Cellules concernées"])
    if deduplicate:
        duplicate = cleaned.duplicated(keep="first")
        reject(cleaned.index[duplicate], "Doublon strict après transformations")
        cleaned = cleaned.loc[~duplicate]
    for reason in sorted({reason for items in reasons.values() for reason in items}):
        record(f"Mise en rejet : {reason}", "Toutes", sum(reason in items for items in reasons.values()))
    rejects = raw.loc[sorted(reasons)].copy()
    # Colonnes de provenance en MultiIndex pour éviter toute collision avec le CSV.
    rejects.columns = pd.MultiIndex.from_tuples([("Donnée source", str(c)) for c in rejects.columns])
    rejects.insert(0, ("Traçabilité", "Enregistrement source"), [int(i)+1 for i in rejects.index])
    rejects.insert(1, ("Traçabilité", "Motifs"), [" ; ".join(reasons[i]) for i in rejects.index])
    return cleaned, rejects, log


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


def records(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso", force_ascii=False))
