"""Étape 3 (Corriger) : appliquer les choix de l'utilisateur, puis résumer le résultat en mots simples.

Entrées : données brutes, dictionnaire, choix faits sur les points repérés à l'étape 2.
Sorties : le plan passé à `pipeline`, les données corrigées et les lignes écartées, le résumé
avant / après et le journal en phrases. Par défaut, rien n'est modifié sans décision.
"""
import pandas as pd

from src.core.dictionnaire import normalize_missing
from src.core.statistiques import numeric_columns
from src.core.texte import pluriel
from src.etape2_comprendre.points import dictionnaire_selon_choix
from src.etape3_corriger.pipeline import pipeline


REGLES_VIDES = {"laisser": "Conserver", "mediane": "Médiane", "inconnu": "Inconnu", "ecarter": "Supprimer les lignes"}


def plan_nettoyage(dictionary, choix, suspects, controles=()):
    """Traduit les choix en paramètres de `pipeline`, sans toucher au dictionnaire reçu.

    `suspects` : tableau des codes repérés par `diagnose` (colonnes « Colonne », « Valeur à vérifier »).
    `controles` : règles du mode expert (`regles_simples`) ; seules celles marquées « écarter » rejettent.
    Retourne {dictionary, missing_rules, deduplicate, conversion_policies, quality_rules, reject_rule_ids, trim}.
    """
    dico, politiques = dictionnaire_selon_choix(dictionary, choix, suspects)
    regles = {col: REGLES_VIDES[decision] for col, decision in choix.get("vides", {}).items()}
    return {"dictionary": dico, "missing_rules": regles,
            "deduplicate": choix.get("doublons", {}).get("doublons") == "une", "conversion_policies": politiques,
            "quality_rules": list(controles),
            "reject_rule_ids": [regle for regle, decision in choix.get("regles", {}).items() if decision == "ecarter"],
            "trim": choix.get("espaces", {}).get("espaces") == "supprimer"}


def choix_complets(points, choix):
    """Choix de chaque point affiché ; la valeur par défaut quand l'utilisateur n'a rien changé."""
    complets = {}
    for point in points:
        for ligne in point["lignes"]:
            options = [cle for cle, _, _ in ligne["options"]]
            valeur = choix.get(point["type"], {}).get(ligne["cle"])
            complets.setdefault(point["type"], {})[ligne["cle"]] = valeur if valeur in options else ligne["defaut"]
    return complets


def decisions(points, choix):
    """Pour le rapport : chaque point affiché, avec le libellé de l'option retenue (défaut si aucun choix)."""
    lignes = []
    for point in points:
        for ligne in point["lignes"]:
            cle = choix.get(point["type"], {}).get(ligne["cle"], ligne["defaut"])
            libelle = next(label for key, label, _ in ligne["options"] if key == cle)
            lignes.append({"titre": point["titre"], "texte": ligne["texte"], "choix": libelle})
    return lignes


def executer(raw, plan):
    """Applique un plan de `plan_nettoyage` sur une copie du brut. Retourne (données corrigées, lignes écartées, journal)."""
    return pipeline(raw, plan["dictionary"], plan.get("quality_rules", []), plan["missing_rules"],
                    deduplicate=plan["deduplicate"], conversion_policies=plan["conversion_policies"],
                    reject_rule_ids=plan.get("reject_rule_ids"), trim=plan.get("trim", False),
                    justification="Choix faits à l'étape Corriger ; actions consignées automatiquement.")


def motif_lisible(motif):
    """Motif de rejet du moteur → phrase simple."""
    if motif.startswith("Valeur manquante : "):
        return f"{motif.removeprefix('Valeur manquante : ')} vide"
    if motif.startswith("Conversion impossible : "):
        return f"{motif.removeprefix('Conversion impossible : ').split(' → ')[0]} : texte au lieu d'un nombre"
    if motif == "Doublon strict après transformations":
        return "copie identique d'une autre ligne"
    for kind in ("Obligatoire", "Unique", "Intervalle"):
        # Rejet par une règle du mode expert : « <libellé de la règle> : <type> ».
        if motif.endswith(f" : {kind}"):
            return f"règle non respectée ({motif.removesuffix(f' : {kind}')})"
    return motif


def resume_resultat(raw, plan, cleaned, rejects):
    """Chiffres avant / après pour l'encadré « Résultat de vos choix ».

    Les cases vides « avant » sont comptées avec les mêmes codes manquants que « après ».
    Les moyennes ne portent que sur les colonnes numériques au rôle Mesure.
    """
    normalized = normalize_missing(raw, plan["dictionary"])
    motifs = rejects[("Traçabilité", "Motifs")].str.split(" ; ").explode() if len(rejects) else pd.Series(dtype=str)
    moyennes = []
    mesures = [d["Colonne"] for d in plan["dictionary"] if d["Rôle"] == "Mesure"]
    for col in [c for c in mesures if c in numeric_columns(cleaned)]:
        avant = pd.to_numeric(normalized[col], errors="coerce").dropna()
        apres = cleaned[col].dropna()
        if len(avant) or len(apres):
            moyennes.append({"colonne": col, "avant": float(avant.mean()) if len(avant) else None, "n_avant": len(avant),
                             "apres": float(apres.mean()) if len(apres) else None, "n_apres": len(apres)})
    return {"total": len(raw), "gardees": len(cleaned), "ecartees": len(rejects),
            "vides_avant": int(normalized.isna().sum().sum()), "vides_apres": int(cleaned.isna().sum().sum()),
            "motifs": [(motif_lisible(m), int(n)) for m, n in motifs.value_counts().items()],
            "moyennes": moyennes}


def regles_signalees(resultats, choix):
    """Règles non respectées dont les lignes sont gardées : [(règle, nombre de lignes)]."""
    return [(regle, len(numeros)) for regle, numeros in resultats.items()
            if numeros and choix.get("regles", {}).get(regle) != "ecarter"]


def phrases_journal(log, signalees=()):
    """Entrées du journal du moteur → phrases simples, dans l'ordre.

    `signalees` : règles du mode expert non respectées mais gardées (`regles_signalees`).
    """
    phrases = []
    for entry in log:
        action, col, n = entry["Action"], entry["Colonne"], entry["Cellules / lignes"]
        if action == "Marqueurs vides normalisés":
            phrases.append(f"{col} : {pluriel(n, 'code reconnu', 'codes reconnus')} comme valeur manquante")
        elif action == "Conversions impossibles : Convertir en vide":
            phrases.append(f"{col} : {pluriel(n, 'texte devenu', 'textes devenus')} une case vide")
        elif action in ("Médiane", "Moyenne"):
            phrases.append(f"{col} : {pluriel(n, 'case vide remplacée', 'cases vides remplacées')} par la {action.lower()}")
        elif action == "Inconnu":
            phrases.append(f"{col} : {pluriel(n, 'case vide remplacée', 'cases vides remplacées')} par « Inconnu »")
        elif action.startswith("Mise en rejet : "):
            phrases.append(f"{pluriel(n, 'ligne mise', 'lignes mises')} de côté : {motif_lisible(action.removeprefix('Mise en rejet : '))}")
        elif action.startswith("Conversion en "):
            phrases.append(f"{col} : traitée comme des nombres")
        elif action == "Espaces de début / fin supprimés":
            phrases.append(f"{col} : espaces en trop supprimés ({pluriel(n, 'valeur')})")
    phrases += [f"{regle} — {pluriel(n, 'ligne signalée', 'lignes signalées')}, gardée{'s' if n > 1 else ''}"
                for regle, n in signalees]
    return phrases or ["Aucun changement : les données restent telles qu'importées."]
