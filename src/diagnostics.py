"""Observer et quantifier les problèmes avant de choisir des corrections."""
import pandas as pd

from src.analysis import numeric_columns
from src.quality import convert, normalize_missing


def diagnose(raw, dictionary):
    normalized = normalize_missing(raw, dictionary)
    prepared = normalized.copy(deep=True)
    rows, suspects, hints = [], [], []
    numeric = numeric_columns(normalized)
    markers = {"?", "na", "n/a", "null", "none", "-", "inconnu"}
    for d in dictionary:
        col = d["Colonne"]
        prepared[col] = convert(normalized[col], d["Type attendu"], d["Format date"])
        invalid = int((normalized[col].notna() & prepared[col].isna()).sum())
        missing = int(normalized[col].isna().sum())
        total_missing = int(prepared[col].isna().sum())
        measure = d["Rôle"] == "Mesure" and col in numeric_columns(prepared)
        values = prepared[col].replace([float("inf"), -float("inf")], float("nan")) if measure else None
        rows.append({"Colonne": col, "Vides détectés": missing,
                     "Vides (%)": round(missing / len(raw)*100, 2) if len(raw) else 0.,
                     "Conversions impossibles": invalid, "Vides après conversion": total_missing,
                     "Moyenne": values.mean() if measure else None,
                     "Médiane": values.median() if measure else None})
        # Tests sur les valeurs distinctes et leurs effectifs, pas cellule par cellule.
        distinct = normalized[col].value_counts()
        labels = pd.Series(distinct.index, dtype=object).astype("string").str.strip()
        counts = (pd.Series(distinct.to_numpy(), index=pd.Index(labels.to_numpy(), dtype=object))
                  .groupby(level=0, sort=False).sum().sort_values(ascending=False, kind="stable"))
        counts = counts.loc[counts.index != ""]
        for token, count in counts.loc[counts.index.str.casefold().isin(markers)].items():
            suspects.append({"Colonne": col, "Valeur à vérifier": token, "Occurrences": int(count)})
        # Constat seulement : le type et le rôle restent décidés par l'utilisateur.
        if d["Type attendu"] == "Conserver" and d["Rôle"] != "Identifiant" and col not in numeric:
            is_number = pd.to_numeric(counts.index.to_series(), errors="coerce").notna().to_numpy()
            filled, numbers = int(counts.sum()), int(counts[is_number].sum())
            if numbers < filled and numbers > filled / 2:
                hints.append({"Colonne": col, "Valeurs renseignées": filled,
                              "Valeurs numériques": numbers,
                              "Valeurs non numériques": filled - numbers,
                              "Exemples non numériques": ", ".join(counts.index[~is_number][:5])})
    return {"normalized": normalized, "prepared": prepared,
            "columns": pd.DataFrame(rows),
            "suspects": pd.DataFrame(suspects, columns=["Colonne", "Valeur à vérifier", "Occurrences"]),
            "numeric_hints": pd.DataFrame(hints, columns=["Colonne", "Valeurs renseignées", "Valeurs numériques",
                                                          "Valeurs non numériques", "Exemples non numériques"])}
