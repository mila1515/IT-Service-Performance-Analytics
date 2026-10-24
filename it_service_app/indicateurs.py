"""Calculs métier sur la table d'incidents préparée : filtres, KPI et tableaux des graphiques.

Les définitions reprennent le notebook 03/05 et les mesures DAX du rapport Power BI.
Chaque KPI indique sa population ; s'il est incalculable, la raison est donnée au lieu d'une valeur.
"""
import pandas as pd

from preparation import ETATS_RESOLUS

CHAMP_PERIODE = "opened_at"
FILTRES = {"priority": "Priorité", "category": "Catégorie", "incident_state": "État", "assignment_group": "Équipe"}
TRANCHES_DELAI = [(0, 4, "< 4 h"), (4, 24, "4 h – 1 j"), (24, 72, "1 – 3 j"), (72, 168, "3 – 7 j"),
                  (168, 720, "7 – 30 j"), (720, float("inf"), "> 30 j")]
MIN_INCIDENTS_EQUIPE = 20  # même seuil que le notebook pour comparer les équipes


def filtrer(incidents, debut=None, fin=None, choix=None):
    """Applique la période (sur opened_at, bornes incluses) et les filtres par valeur (liste vide = tout)."""
    masque = pd.Series(True, index=incidents.index)
    if debut is not None:
        masque &= incidents[CHAMP_PERIODE].dt.date >= debut
    if fin is not None:
        masque &= incidents[CHAMP_PERIODE].dt.date <= fin
    for col, valeurs in (choix or {}).items():
        if valeurs and col in incidents.columns:
            masque &= incidents[col].isin(valeurs)
    return incidents[masque]


def _kpi(nom, valeur, unite, definition, population, raison=None):
    return {"indicateur": nom, "valeur": valeur, "unité": unite, "définition": definition,
            "population": population, "indisponible": raison}


def _absente(df, col):
    return col not in df.columns or df[col].isna().all()


def calculer_kpi(df):
    """Liste des KPI (dict) pour la table filtrée df."""
    n = df["number"].nunique()
    kpis = [_kpi("Incidents uniques", n, "incidents", "Nombre de numéros d'incident distincts.",
                 "Tous les incidents filtrés")]
    if n == 0:
        return kpis

    if "incident_state" in df.columns:
        resolus = int(df["incident_state"].isin(ETATS_RESOLUS).sum())
        kpis += [_kpi("Incidents résolus", resolus, "incidents", "Dernier état Resolved ou Closed.",
                      f"{format_fr(n)} incidents"),
                 _kpi("Incidents ouverts", n - resolus, "incidents", "Dernier état autre que Resolved ou Closed.",
                      f"{format_fr(n)} incidents")]
    else:
        raison = "Colonne incident_state absente."
        kpis += [_kpi("Incidents résolus", None, "incidents", "Dernier état Resolved ou Closed.", "-", raison),
                 _kpi("Incidents ouverts", None, "incidents", "Dernier état autre que Resolved ou Closed.", "-", raison)]

    delais = df["resolution_time_hours"].dropna()
    pop = f"{format_fr(len(delais))} incidents avec des dates d'ouverture et de résolution valides et cohérentes"
    raison = None if len(delais) else "Aucun incident avec des dates d'ouverture et de résolution valides."
    kpis += [_kpi("Délai moyen de résolution", _arrondi(delais.mean()), "heures",
                  "Moyenne de resolved_at − opened_at.", pop, raison),
             _kpi("Délai médian de résolution", _arrondi(delais.median()), "heures",
                  "Moitié des incidents résolus plus vite que cette durée ; peu sensible aux cas extrêmes.", pop, raison)]

    cloture = df["closure_time_hours"].dropna()
    kpis.append(_kpi("Délai moyen de clôture", _arrondi(cloture.mean()), "heures",
                     "Moyenne de closed_at − opened_at, incidents à l'état Closed.",
                     f"{format_fr(len(cloture))} incidents clos avec des dates valides",
                     None if len(cloture) else "Aucun incident clos avec des dates valides."))

    if _absente(df, "sla_compliant"):
        raison = "Pas de statut SLA exploitable (colonne made_sla absente ou vide) : aucun objectif à comparer."
        kpis += [_kpi("Respect des SLA", None, "%", "Part des incidents avec made_sla = True.", "-", raison),
                 _kpi("Respect des SLA (résolus)", None, "%", "Même calcul, incidents résolus seulement.", "-", raison)]
    else:
        sla = df["sla_compliant"].dropna()
        kpis.append(_kpi("Respect des SLA", _pourcent(sla.mean()), "%",
                         "Part des incidents avec made_sla = True.",
                         f"{format_fr(len(sla))} incidents avec un statut SLA, ouverts compris"))
        if "incident_state" in df.columns:
            sla_res = df.loc[df["incident_state"].isin(ETATS_RESOLUS), "sla_compliant"].dropna()
            kpis.append(_kpi("Respect des SLA (résolus)", _pourcent(sla_res.mean()) if len(sla_res) else None, "%",
                             "Même calcul limité aux incidents Resolved ou Closed.",
                             f"{format_fr(len(sla_res))} incidents résolus avec un statut SLA",
                             None if len(sla_res) else "Aucun incident résolu dans la sélection."))

    if _absente(df, "reassignment_count"):
        raison = ("Colonne reassignment_count absente ou vide. Le nombre d'événements n'est pas utilisé à la place : "
                  "un événement n'est pas forcément une réassignation.")
        kpis += [_kpi("Taux d'incidents réassignés", None, "%", "Part des incidents réassignés au moins une fois.", "-", raison),
                 _kpi("Réassignations moyennes", None, "par incident", "Moyenne de reassignment_count.", "-", raison)]
    else:
        compte = df["reassignment_count"].dropna()
        pop = f"{format_fr(len(compte))} incidents avec un compteur renseigné"
        kpis += [_kpi("Taux d'incidents réassignés", _pourcent((compte > 0).mean()), "%",
                      "Part des incidents avec reassignment_count > 0.", pop),
                 _kpi("Réassignations moyennes", _arrondi(compte.mean()), "par incident",
                      "Moyenne du compteur reassignment_count au dernier état.", pop)]

    if not _absente(df, "reopen_count"):
        compte = df["reopen_count"].dropna()
        kpis.append(_kpi("Réouvertures moyennes", _arrondi(compte.mean()), "par incident",
                         "Moyenne du compteur reopen_count au dernier état.", f"{format_fr(len(compte))} incidents"))
    return kpis


def _arrondi(valeur):
    return None if pd.isna(valeur) else round(float(valeur), 2)


def _pourcent(valeur):
    return None if pd.isna(valeur) else round(float(valeur) * 100, 2)


# --- Tableaux pour les graphiques -------------------------------------------------------------

def volume_par_mois(df):
    return (df.dropna(subset=["opened_month"]).groupby("opened_month").size()
            .reset_index(name="incidents").rename(columns={"opened_month": "mois"}))


def repartition(df, colonne, limite=None):
    """Incidents par valeur de colonne, du plus fréquent au moins fréquent ; le reste regroupé en « Autres »."""
    compte = df[colonne].value_counts(dropna=False).rename_axis(colonne).reset_index(name="incidents")
    compte[colonne] = compte[colonne].fillna("Non renseigné").astype(str)
    if limite and len(compte) > limite:
        autres = pd.DataFrame({colonne: [f"Autres ({len(compte) - limite})"],
                               "incidents": [compte["incidents"].iloc[limite:].sum()]})
        compte = pd.concat([compte.head(limite), autres], ignore_index=True)
    return compte


def tranches_delai(df):
    """Nombre d'incidents par tranche de délai de résolution (ordre croissant des tranches)."""
    delais = df["resolution_time_hours"].dropna()
    lignes = [{"tranche": nom, "ordre": i, "incidents": int(((delais >= bas) & (delais < haut)).sum())}
              for i, (bas, haut, nom) in enumerate(TRANCHES_DELAI)]
    return pd.DataFrame(lignes)


def resume(df, colonne):
    """Incidents, SLA (%) et délais de résolution par valeur de colonne (fonction summarize du notebook 05).

    Le SLA ignore les incidents sans statut SLA ; les délais, les incidents sans délai valide.
    """
    stats = (df.groupby(colonne, dropna=False)
             .agg(incidents=("number", "nunique"), sla_pct=("sla_compliant", "mean"),
                  resolution_moyenne_h=("resolution_time_hours", "mean"),
                  resolution_mediane_h=("resolution_time_hours", "median"))
             .reset_index())
    stats["sla_pct"] = (stats["sla_pct"].astype(float) * 100).round(2)
    stats[["resolution_moyenne_h", "resolution_mediane_h"]] = (
        stats[["resolution_moyenne_h", "resolution_mediane_h"]].astype(float).round(2))
    return stats


def sla_par_priorite(df):
    if "priority" not in df.columns:
        return pd.DataFrame()
    return resume(df, "priority").sort_values("priority")


def sla_par_mois(df):
    return resume(df.dropna(subset=["opened_month"]), "opened_month").rename(columns={"opened_month": "mois"})


def effet_reassignation(df):
    """Incidents avec et sans réassignation : volume, SLA et délais (notebooks 03 à 05)."""
    if _absente(df, "reassignment_count"):
        return pd.DataFrame()
    statut = df["has_reassignment"].map({True: "Avec réassignation", False: "Sans réassignation"})
    return resume(df.assign(reassignment_status=statut).dropna(subset=["reassignment_status"]),
                  "reassignment_status").sort_values("reassignment_status", ascending=False)


def sla_par_equipe(df, top=15):
    """SLA des équipes ayant au moins MIN_INCIDENTS_EQUIPE incidents, les plus chargées d'abord."""
    if "assignment_group" not in df.columns or _absente(df, "sla_compliant"):
        return pd.DataFrame()
    stats = resume(df, "assignment_group")
    return stats[stats["incidents"] >= MIN_INCIDENTS_EQUIPE].nlargest(top, "incidents")


def plus_longs(df, top=25):
    """Incidents au délai de résolution le plus long (requête « incidents les plus longs » du notebook 04)."""
    colonnes = [c for c in ["number", "resolution_time_hours", "assignment_group", "category", "priority",
                            "incident_state"] if c in df.columns]
    return df.dropna(subset=["resolution_time_hours"]).nlargest(top, "resolution_time_hours")[colonnes]


def plus_reassignes(df, top=20):
    if _absente(df, "reassignment_count"):
        return pd.DataFrame()
    colonnes = [c for c in ["number", "reassignment_count", "assignment_group", "category", "priority",
                            "incident_state", "resolution_time_hours"] if c in df.columns]
    lignes = df.dropna(subset=["reassignment_count"])
    return lignes[lignes["reassignment_count"] > 0].nlargest(top, "reassignment_count")[colonnes]


def format_fr(valeur, unite=""):
    """Format français : 24 918 · 63,45 % · 178,17 h ; « — » si la valeur manque."""
    if valeur is None or pd.isna(valeur):
        return "—"
    texte = f"{valeur:,.2f}" if isinstance(valeur, float) else f"{valeur:,}"
    texte = texte.replace(",", " ").replace(".", ",")
    return {"%": f"{texte} %", "heures": f"{texte} h"}.get(unite, texte)


# --- Lecture des résultats ----------------------------------------------------------------------
ECART_SLA_POINTS = 10   # une priorité est signalée si son SLA est au moins 10 points sous le taux global
PART_MOIS_FAIBLE = 0.01  # un mois sous 1 % des incidents rend la tendance mensuelle fragile


def lecture(df, kpis):
    """Messages courts, calculés sur la sélection filtrée, dans l'esprit du notebook 05.

    Un message n'est produit que si les données le permettent ; aucun seuil n'est caché (constantes ci-dessus).
    """
    messages = []
    par_nom = {k["indicateur"]: k["valeur"] for k in kpis}
    sla = par_nom.get("Respect des SLA")
    if sla is not None:
        messages.append(f"Le taux de respect des SLA est de **{format_fr(sla, '%')}** sur la sélection.")

        priorites = sla_par_priorite(df).dropna(subset=["sla_pct"])
        faibles = priorites[priorites["sla_pct"] <= sla - ECART_SLA_POINTS]
        if not faibles.empty:
            liste = ", ".join(f"`{p}` ({format_fr(v, '%')}, {format_fr(n)} incidents)"
                              for p, v, n in faibles[["priority", "sla_pct", "incidents"]].itertuples(index=False))
            messages.append(f"Priorités au moins {ECART_SLA_POINTS} points sous ce taux : {liste}. "
                            "Ce sont les points de contrôle prioritaires.")

        equipes = sla_par_equipe(df).dropna(subset=["sla_pct"])
        if len(equipes) >= 2:
            basse = equipes.nsmallest(1, "sla_pct").iloc[0]
            chargee = equipes.iloc[0]
            messages.append(f"Équipe la plus chargée : `{chargee['assignment_group']}` "
                            f"({format_fr(int(chargee['incidents']))} incidents, SLA {format_fr(chargee['sla_pct'], '%')}). "
                            f"SLA le plus bas parmi les {len(equipes)} équipes les plus chargées : "
                            f"`{basse['assignment_group']}` ({format_fr(basse['sla_pct'], '%')}).")

    effet = effet_reassignation(df)
    if len(effet) == 2:
        avec, sans = (effet.set_index("reassignment_status").loc[s] for s in ("Avec réassignation", "Sans réassignation"))
        if pd.notna(avec["resolution_moyenne_h"]) and pd.notna(sans["resolution_moyenne_h"]):
            texte = (f"Les incidents réassignés sont résolus en **{format_fr(avec['resolution_moyenne_h'], 'heures')}** "
                     f"en moyenne, contre {format_fr(sans['resolution_moyenne_h'], 'heures')} sans réassignation")
            if pd.notna(avec["sla_pct"]) and pd.notna(sans["sla_pct"]):
                texte += f" ; SLA {format_fr(avec['sla_pct'], '%')} contre {format_fr(sans['sla_pct'], '%')}"
            messages.append(texte + ". Mieux qualifier et router les incidents dès l'ouverture peut réduire ces délais.")

    moyenne, mediane = par_nom.get("Délai moyen de résolution"), par_nom.get("Délai médian de résolution")
    if moyenne and mediane and moyenne > 2 * mediane:
        messages.append(f"Délai médian de {format_fr(mediane, 'heures')} contre une moyenne de "
                        f"{format_fr(moyenne, 'heures')} : quelques incidents très longs tirent la moyenne vers le haut "
                        "(voir « Incidents les plus longs »).")

    mois = volume_par_mois(df)
    faibles = mois[mois["incidents"] < PART_MOIS_FAIBLE * mois["incidents"].sum()]
    if len(mois) > 1 and not faibles.empty:
        messages.append(f"{len(faibles)} mois sur {len(mois)} contiennent moins de {PART_MOIS_FAIBLE * 100:g} % des incidents : "
                        "la tendance mensuelle est à lire avec prudence.")
    return messages


def recapitulatif_kpi(kpis, description_filtres):
    """Tableau exportable des KPI, avec les filtres actifs sur chaque ligne."""
    recap = pd.DataFrame(kpis)
    recap["filtres"] = description_filtres
    return recap
