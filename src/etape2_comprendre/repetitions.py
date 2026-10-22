"""Étape 2 (Comprendre) : pourquoi un identifiant se répète-t-il ? Diagnostic en lecture seule.

Entrées : données (codes manquants déjà devenus des cases vides) et la colonne qui sert de clé.
Sortie : les groupes de lignes qui partagent une même valeur de clé, la part des groupes où
chaque autre colonne change, et un exemple de groupe. Rien n'est modifié ; un identifiant
répété n'est pas présenté comme une erreur.
"""
from src.config import LIGNES_APERCU


def variations(data, colonne):
    """Ce qui change entre les lignes d'un même identifiant, ou None si aucune valeur ne se répète.

    Retourne {groupes, lignes, changent: [(colonne, part des groupes)], identiques: [colonnes],
    exemple, exemple_total, exemple_lignes}. Une case vide face à une valeur compte comme un changement.
    """
    cle = data[colonne]
    repetees = data.loc[cle.notna() & cle.duplicated(keep=False)]
    if repetees.empty:
        return None
    autres = [c for c in data.columns if c != colonne]
    par_groupe = repetees.groupby(colonne, sort=False, observed=True)[autres].nunique(dropna=False)
    parts = (par_groupe > 1).mean().sort_values(ascending=False, kind="stable")
    changent = [(c, float(p)) for c, p in parts.items() if p > 0]
    exemple = repetees[colonne].value_counts().index[0]
    lignes_exemple = repetees.loc[repetees[colonne] == exemple, [colonne] + [c for c, _ in changent]]
    return {"groupes": len(par_groupe), "lignes": len(repetees), "changent": changent,
            "identiques": [c for c, p in parts.items() if p == 0], "exemple": str(exemple),
            "exemple_total": len(lignes_exemple), "exemple_lignes": lignes_exemple.head(LIGNES_APERCU)}


def part_lisible(part):
    """0.983 → « 98 % », 0.004 → « moins de 1 % », 0.996 → « 99 % » (100 % seulement si c'est tous)."""
    if part >= 1:
        return "100 %"
    pourcent = round(part * 100)
    return "moins de 1 %" if pourcent == 0 else f"{min(pourcent, 99)} %"
