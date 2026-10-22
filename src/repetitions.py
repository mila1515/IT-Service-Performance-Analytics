"""Diagnostic générique des clés répétées, sans transformation des données."""
import json

import pandas as pd


SUMMARY_COLUMNS = ["Groupe", "Valeurs de la clé", "Lignes", "Doublons stricts en excès",
                   "Clés de ligne répétées", "Groupes avec différences", "Détails incomplets",
                   "Colonnes différentes", "Lecture proposée"]


def inspect_repetitions(data, keys, detail_keys=None, compare_columns=None, source=None):
    detail_keys = list(detail_keys or [])
    keys = list(keys)
    leaf_keys = keys + detail_keys
    if not keys or len(set(leaf_keys)) != len(leaf_keys) or any(c not in data for c in leaf_keys):
        raise ValueError("Choisissez une clé existante et des colonnes de détail distinctes.")
    compared = list(compare_columns) if compare_columns is not None else [c for c in data if c not in leaf_keys]
    if len(set(compared)) != len(compared) or any(c not in data or c in leaf_keys for c in compared):
        raise ValueError("Les champs comparés doivent être distincts des clés.")
    complete = data[keys].notna().all(axis=1)
    repeated = data.loc[complete & data.duplicated(subset=keys, keep=False)]
    rows, membership, differences = [], [], []
    # Les identifiants internes restent séparés des noms du CSV.
    for number, (values, group) in enumerate(repeated.groupby(keys, sort=False, observed=True, dropna=False), start=1):
        values = values if isinstance(values, tuple) else (values,)
        group_id = f"G{number:05d}"
        original = source.loc[group.index] if source is not None else group
        exact = len(group)-len(original.drop_duplicates())
        detail_complete = group[detail_keys].notna().all(axis=1) if detail_keys else pd.Series(True, index=group.index)
        leaves = group.loc[detail_complete]
        n_repeated = 0
        conflicts = 0
        changed = set()
        for _, leaf in leaves.groupby(leaf_keys, sort=False, observed=True, dropna=False):
            if len(leaf) < 2:
                continue
            n_repeated += 1
            varying = [c for c in compared if leaf[c].nunique(dropna=False) > 1]
            if varying:
                conflicts += 1
                changed.update(varying)
                for col in varying:
                    differences.append({"Groupe": group_id, "Clé de ligne": json.dumps({c: str(leaf[c].iloc[0]) for c in leaf_keys}, ensure_ascii=False),
                                        "Colonne": col, "Valeurs distinctes": int(leaf[col].nunique(dropna=False))})
        incomplete = int((~detail_complete).sum())
        if incomplete:
            status = "Détail incomplet — à investiguer"
        elif detail_keys and not n_repeated:
            status = "Lignes distinctes selon le détail choisi"
        elif conflicts:
            status = "Même clé de ligne — valeurs différentes"
        elif exact:
            status = "Doublons stricts potentiels"
        else:
            status = "Même clé de ligne — champs non comparés à vérifier"
        rows.append({"Groupe": group_id, "Valeurs de la clé": json.dumps({c: str(v) for c, v in zip(keys, values)}, ensure_ascii=False),
                     "Lignes": len(group), "Doublons stricts en excès": exact,
                     "Clés de ligne répétées": n_repeated, "Groupes avec différences": conflicts,
                     "Détails incomplets": incomplete, "Colonnes différentes": ", ".join(c for c in compared if c in changed),
                     "Lecture proposée": status})
        membership += [{"Groupe": group_id, "Enregistrement source": int(i)+1} for i in group.index]
    return {"summary": pd.DataFrame(rows, columns=SUMMARY_COLUMNS),
            "membership": pd.DataFrame(membership, columns=["Groupe", "Enregistrement source"]),
            "differences": pd.DataFrame(differences, columns=["Groupe", "Clé de ligne", "Colonne", "Valeurs distinctes"]),
            "incomplete": [int(i)+1 for i in data.index[~complete]]}
