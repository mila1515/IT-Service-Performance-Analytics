"""Étape 3 : traitements choisis par l'utilisateur, appliqués sur une copie du brut, avec rejets tracés."""


from datetime import datetime, timezone

import pandas as pd

from src.core.dictionnaire import convert, normalize_missing
from src.core.regles import audit
from src.core.statistiques import numeric_columns


def clean(data, rules):
    """Remplacements choisis par colonne, calculés sur les lignes reçues.

    Les espaces, doublons et suppressions de lignes sont traités par pipeline() (mises en rejet).
    """
    result = data.copy(deep=True)
    log = []
    for col, rule in rules.items():
        count = int(data[col].isna().sum())
        if rule in ("Conserver", "Supprimer les lignes") or not count:
            continue
        if rule in ("Moyenne", "Médiane"):
            if col not in numeric_columns(data):
                raise ValueError(f"{col} : remplacement numérique impossible.")
            value = data[col].mean() if rule == "Moyenne" else data[col].median()
            if pd.isna(value):
                raise ValueError(f"{col} : aucune valeur pour calculer le remplacement.")
            result[col] = result[col].astype(float).fillna(value)
        elif rule == "Inconnu":
            result[col] = result[col].astype("string").fillna("Inconnu")
        else:
            raise ValueError(f"Règle inconnue : {rule}")
        log.append({"Colonne": col, "Action": rule, "Cellules concernées": count})
    return result, log


def pipeline(raw, dictionary, quality_rules, missing_rules, *, trim=False, deduplicate=False,
             conversion_policy="Bloquer", reject_rule_ids=None, justification="", owner="",
             conversion_policies=None):
    """`conversion_policies` : politique propre à certaines colonnes ; les autres suivent `conversion_policy`."""
    conversion_policies = conversion_policies or {}
    if {conversion_policy, *conversion_policies.values()} - {"Bloquer", "Mettre en rejet", "Convertir en vide"}:
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
        policy = conversion_policies.get(col, conversion_policy)
        if failed.any():
            if policy == "Bloquer":
                raise ValueError(f"{col} : {int(failed.sum())} conversions impossibles. Corrigez le type/format ou choisissez explicitement leur traitement.")
            if policy == "Mettre en rejet":
                reject(work.index[failed], f"Conversion impossible : {col} → {target}")
            record(f"Conversions impossibles : {policy}", col, failed.sum())
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
