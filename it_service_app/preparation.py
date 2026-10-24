"""Préparation des données IT Service : lecture, contrôles et table « une ligne par incident ».

Reprend les règles du notebook 02_Data_Cleaning (corrigé le 24/10/2026) : ex-aequo sur le dernier état départagés
par sys_mod_count, made_sla vide laissé manquant. Deux protections en plus, sans effet sur les données du projet
(voir README) : un sys_updated_at invalide n'est jamais retenu comme « dernier état », et le délai de clôture
n'est calculé que pour les incidents à l'état Closed.
Aucune ligne n'est supprimée sans être comptée dans le rapport de contrôles.
"""
import io

import numpy as np
import pandas as pd

# Colonnes sans lesquelles l'application ne peut rien calculer.
COLONNES_REQUISES = ["number", "opened_at"]
# Colonnes utiles : leur absence rend seulement certains indicateurs indisponibles.
COLONNES_UTILES = {
    "incident_state": "état de l'incident (ouverts / résolus, clôture)",
    "resolved_at": "date de résolution (délai de résolution)",
    "closed_at": "date de clôture (délai de clôture)",
    "made_sla": "statut SLA ServiceNow (respect des SLA)",
    "reassignment_count": "compteur de réassignations",
    "reopen_count": "compteur de réouvertures",
    "priority": "priorité (filtre et répartition)",
    "category": "catégorie (filtre et répartition)",
    "assignment_group": "équipe support (filtre et SLA par équipe)",
    "sys_updated_at": "date de mise à jour (choix du dernier état d'un journal)",
    "sys_mod_count": "compteur de modifications (départage des ex-aequo)",
}
COLONNES_DATES = ["opened_at", "resolved_at", "closed_at", "sys_created_at", "sys_updated_at"]
# Format du fichier brut d'abord (notebook), puis celui des exports pandas (incident_clean.csv).
FORMATS_DATES = ["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d"]
TEXTES_INCONNU = ["category", "subcategory", "assignment_group", "contact_type", "location"]
TEXTES_NON_ASSIGNE = ["assigned_to", "resolved_by", "opened_by"]
COMPTEURS = ["reassignment_count", "reopen_count", "sys_mod_count"]
# Colonnes ajoutées par le notebook, dans le même ordre que incident_clean.csv (lu par Power BI).
COLONNES_CALCULEES = ["priority_level", "impact_level", "urgency_level", "resolution_time_hours",
                      "closure_time_hours", "sla_compliant", "has_reassignment", "has_reopen",
                      "opened_month", "opened_hour"]
ETATS_RESOLUS = ["Resolved", "Closed"]


class FichierIncompatible(Exception):
    """Le fichier ne peut pas être analysé ; le message explique pourquoi."""


def lire_csv(contenu):
    """Lit le CSV comme le notebook (« ? » = manquant) ; essaie « ; » et l'encodage Windows si besoin."""
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            data = pd.read_csv(io.BytesIO(contenu), na_values=["?"], low_memory=False, encoding=encodage)
            if len(data.columns) == 1 and ";" in str(data.columns[0]):
                data = pd.read_csv(io.BytesIO(contenu), sep=";", na_values=["?"], low_memory=False, encoding=encodage)
            return data
        except UnicodeDecodeError:
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as erreur:
            raise FichierIncompatible(f"Le fichier n'est pas un CSV lisible : {erreur}") from erreur
    raise FichierIncompatible("Encodage du fichier non reconnu (ni UTF-8, ni Windows-1252).")


def verifier_colonnes(data):
    """Retourne (colonnes utiles absentes avec leur rôle) ; lève FichierIncompatible si une colonne requise manque."""
    manquantes = [c for c in COLONNES_REQUISES if c not in data.columns]
    if manquantes:
        raise FichierIncompatible(
            f"Colonnes obligatoires absentes : {', '.join(manquantes)}. "
            f"Colonnes trouvées : {', '.join(map(str, data.columns[:15]))}{'…' if len(data.columns) > 15 else ''}")
    return {c: role for c, role in COLONNES_UTILES.items() if c not in data.columns}


def valeurs_manquantes(data):
    """Valeurs manquantes par colonne du fichier importé (« ? » compris), de la plus incomplète à la moins incomplète.

    Même tableau que le notebook 01, limité aux colonnes qui ont au moins une valeur manquante.
    """
    tableau = pd.DataFrame({"colonne": data.columns, "type": [str(t) for t in data.dtypes],
                            "valeurs_manquantes": data.isna().sum().values,
                            "taux_manquant_pct": (data.isna().mean().values * 100).round(2)})
    tableau = tableau[tableau["valeurs_manquantes"] > 0]
    return tableau.sort_values("valeurs_manquantes", ascending=False).reset_index(drop=True)


def convertir_date(serie):
    """Convertit une colonne de dates avec le format qui en lit le plus. Retourne (dates, format, nb invalides)."""
    texte = serie.astype("string").str.strip()
    renseignees = texte.notna() & (texte != "")
    meilleur, meilleur_format = pd.Series(pd.NaT, index=serie.index), None
    for fmt in FORMATS_DATES:
        essai = pd.to_datetime(texte, format=fmt, errors="coerce")
        if essai.notna().sum() > meilleur.notna().sum():
            meilleur, meilleur_format = essai, fmt
    invalides = int((renseignees & meilleur.isna()).sum())
    return meilleur, meilleur_format, invalides


def convertir_sla(serie):
    """true/false (quelle que soit la casse) → booléen ; toute autre valeur reste manquante."""
    texte = serie.astype("string").str.strip().str.lower()
    return texte.map({"true": True, "false": False}).astype("boolean")


def niveau(valeur):
    """« 3 - Moderate » → 3 (même règle que le notebook)."""
    if pd.isna(valeur):
        return np.nan
    return pd.to_numeric(str(valeur).split(" - ")[0], errors="coerce")


def _controle(controles, nom, valeur, effet):
    controles.append({"contrôle": nom, "valeur": int(valeur), "effet sur les calculs": effet})


def preparer(data):
    """Construit la table d'incidents. Retourne (incidents, controles, infos).

    incidents : une ligne par incident, colonnes de incident_clean.csv ;
    controles : tableau des anomalies et exclusions, chiffrées ;
    infos : format détecté, formats de dates, colonnes absentes.
    """
    colonnes_absentes = verifier_colonnes(data)
    df = data.copy()
    controles = []
    infos = {"lignes": len(df), "colonnes": len(df.columns), "colonnes_absentes": colonnes_absentes, "formats_dates": {},
             "manquants": valeurs_manquantes(data)}

    # Identifiant : une ligne sans numéro ne peut être rattachée à aucun incident.
    df["number"] = df["number"].astype("string").str.strip()
    sans_numero = df["number"].isna() | (df["number"] == "")
    _controle(controles, "Lignes sans numéro d'incident", sans_numero.sum(), "Exclues : rattachement impossible")
    df = df[~sans_numero]
    if df.empty:
        raise FichierIncompatible("Aucune ligne ne porte de numéro d'incident (colonne number vide).")

    for col in [c for c in COLONNES_DATES if c in df.columns]:
        df[col], fmt, invalides = convertir_date(df[col])
        infos["formats_dates"][col] = fmt
        _controle(controles, f"Dates invalides : {col}", invalides, "Traitées comme manquantes")

    # Événements multiples (journal) ou vrais doublons (lignes strictement identiques).
    lignes_par_incident = df["number"].value_counts()
    infos["incidents"] = int(lignes_par_incident.size)
    infos["lignes_par_incident"] = round(len(df) / lignes_par_incident.size, 2)
    infos["periode"] = (df["opened_at"].min(), df["opened_at"].max())
    infos["format"] = "journal d'événements" if (lignes_par_incident > 1).any() else "table d'incidents"
    _controle(controles, "Lignes strictement identiques (vrais doublons)", data.duplicated().sum(),
              "Sans effet : une seule ligne est gardée par incident")
    _controle(controles, "Incidents présents sur plusieurs lignes (événements)", (lignes_par_incident > 1).sum(),
              "Réduits à leur dernier état connu")

    if infos["format"] == "journal d'événements":
        if "sys_updated_at" not in df.columns:
            raise FichierIncompatible("Plusieurs lignes par incident mais pas de colonne sys_updated_at : "
                                      "impossible de savoir quelle ligne est le dernier état.")
        cles = ["number", "sys_updated_at"] + (["sys_mod_count"] if "sys_mod_count" in df.columns else [])
        maximum = df.groupby("number")["sys_updated_at"].transform("max")
        ex_aequo = df[df["sys_updated_at"] == maximum].groupby("number").size().gt(1).sum()
        departage = "sys_mod_count le plus élevé" if "sys_mod_count" in df.columns else "ordre du fichier"
        _controle(controles, "Incidents dont le dernier état est ex-aequo", ex_aequo, f"Départagés par {departage}")
        # Tri stable, dates invalides en premier : elles ne sont jamais prises pour le dernier état.
        tri = df.assign(_ordre=np.arange(len(df)))
        if "sys_mod_count" in tri.columns:
            tri["sys_mod_count"] = pd.to_numeric(tri["sys_mod_count"], errors="coerce")
        tri = tri.sort_values(cles + ["_ordre"], kind="mergesort", na_position="first")
        df = tri.drop_duplicates(subset="number", keep="last").drop(columns="_ordre")
    df = df.drop(columns=[c for c in COLONNES_CALCULEES if c in df.columns]).reset_index(drop=True)

    # Valeurs manquantes : mêmes libellés que le notebook, mais comptés.
    for col, libelle in [(c, "Inconnu") for c in TEXTES_INCONNU] + [(c, "Non assigne") for c in TEXTES_NON_ASSIGNE]:
        if col in df.columns:
            _controle(controles, f"Valeurs manquantes : {col}", df[col].isna().sum(), f"Affichées « {libelle} »")
            df[col] = df[col].fillna(libelle)
    for col in [c for c in COMPTEURS if c in df.columns]:
        valeurs = pd.to_numeric(df[col], errors="coerce")
        _controle(controles, f"Compteur vide ou non numérique : {col}", valeurs.isna().sum(),
                  "Exclu des moyennes concernées")
        df[col] = valeurs.round().astype("Int64")
    if "made_sla" in df.columns:
        df["made_sla"] = convertir_sla(df["made_sla"])
        _controle(controles, "Statut SLA vide ou illisible (made_sla)", df["made_sla"].isna().sum(),
                  "Exclu du taux de respect des SLA")

    for col in ["priority", "impact", "urgency"]:
        df[f"{col}_level"] = df[col].apply(niveau) if col in df.columns else np.nan

    # Délais en heures ; une durée négative est incohérente et n'est pas utilisée.
    df["resolution_time_hours"] = _duree(df, "resolved_at", controles, "résolution")
    duree_cloture = _duree(df, "closed_at", controles, "clôture")
    if "incident_state" in df.columns:
        pas_clos = duree_cloture.notna() & (df["incident_state"] != "Closed")
        _controle(controles, "Date de clôture renseignée sur un incident non clos", pas_clos.sum(),
                  "Exclu du délai de clôture")
        duree_cloture = duree_cloture.mask(pas_clos)
    df["closure_time_hours"] = duree_cloture
    if "resolved_at" in df.columns:
        _controle(controles, "Incidents sans date de résolution valide", df["resolved_at"].isna().sum(),
                  "Exclus des délais de résolution")
    _controle(controles, "Incidents sans date d'ouverture valide", df["opened_at"].isna().sum(),
              "Exclus des délais et du filtre de période")

    df["sla_compliant"] = (df["made_sla"].astype("Int64") if "made_sla" in df.columns
                           else pd.Series(pd.NA, index=df.index, dtype="Int64"))
    df["has_reassignment"] = _au_moins_un(df, "reassignment_count")
    df["has_reopen"] = _au_moins_un(df, "reopen_count")
    df["opened_month"] = df["opened_at"].dt.to_period("M").astype("string")
    df["opened_hour"] = df["opened_at"].dt.hour.astype("Int64")

    if "assignment_group" in df.columns:
        _controle(controles, "Incidents sans équipe (« Inconnu »)", (df["assignment_group"] == "Inconnu").sum(),
                  "Gardés et affichés comme une équipe à part")
    return df, pd.DataFrame(controles), infos


def _duree(df, colonne_fin, controles, nom):
    """Heures entre opened_at et colonne_fin, arrondies à 2 décimales ; négatives → manquantes (comptées)."""
    if colonne_fin not in df.columns:
        return pd.Series(np.nan, index=df.index)
    heures = (df[colonne_fin] - df["opened_at"]).dt.total_seconds() / 3600
    _controle(controles, f"Délais de {nom} négatifs", (heures < 0).sum(), "Exclus des délais")
    return heures.mask(heures < 0).round(2)


def _au_moins_un(df, colonne):
    if colonne not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="boolean")
    return (df[colonne] > 0).astype("boolean")
