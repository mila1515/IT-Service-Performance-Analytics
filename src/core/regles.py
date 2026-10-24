"""Contrôles qualité avec références aux enregistrements sources.

Utilisé par les règles facultatives de l'étape Comprendre (règles simples : remplie, unique, entre deux bornes)
et par le pipeline de l'étape Corriger.
"""


import json

import pandas as pd

from src.core.dictionnaire import convert, normalize_missing
from src.core.texte import nombre_lisible

AUDIT_COLUMNS = ["ID", "Colonne", "Dimension", "Règle", "Seuil (%)", "Anomalies", "Lignes", "Taux (%)", "Statut", "Priorité"]


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
            if rule.get("ignore_text"):
                # Règles facultatives : un texte non numérique a déjà sa propre carte, il n'est pas compté ici.
                bad &= numbers.notna()
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


def _controle(colonne, kind, libelle):
    # Priorité et seuil fixes : pour les règles facultatives, toute ligne qui ne respecte pas est signalée.
    return {"id": libelle, "column": colonne, "kind": kind, "priority": "P2", "threshold": 0.}


def regles_simples(regles):
    """Règles facultatives cochées à l'étape Comprendre → contrôles pour `audit` (l'identifiant est le libellé lisible).

    `regles` : {colonne: {"remplie": bool, "unique": bool, "bornes": [minimum, maximum] ou None}}.
    """
    controles = []
    for colonne, regle in regles.items():
        if regle.get("remplie"):
            controles.append(_controle(colonne, "Obligatoire", f"{colonne} : doit être remplie"))
        if regle.get("unique"):
            controles.append(_controle(colonne, "Unique", f"{colonne} : valeurs uniques"))
        if regle.get("bornes"):
            bas, haut = sorted(float(b) for b in regle["bornes"])
            controle = _controle(colonne, "Intervalle", f"{colonne} : entre {nombre_lisible(bas)} et {nombre_lisible(haut)}")
            controles.append({**controle, "low": bas, "high": haut, "ignore_text": True})
    return controles

