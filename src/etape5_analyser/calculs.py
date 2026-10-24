"""Étape 5 (Analyser) : comparer des groupes, mesurer un délai, suivre une évolution.

Entrées : données préparées (types de l'étape Comprendre, sortie de `prepare`) et les colonnes
choisies par l'utilisateur. Sorties : tableaux classés, données des graphiques et constats.
Aucune règle métier : un constat décrit les chiffres et ne donne jamais de cause. Les données ne
sont pas modifiées (copies ou vues seulement).
"""
import pandas as pd

from src.config import CATEGORIES_GRAPHIQUE, GROUPE_MIN_COMPARAISON, LIBELLE_MANQUANT
from src.core.dates import compter_par_periode
from src.core.texte import nombre_lisible, pluriel
from src.etape2_comprendre.repetitions import part_lisible

STATISTIQUES = {"nombre": "Nombre", "moyenne": "Moyenne", "mediane": "Médiane"}
UNITES_DELAI = {"jours": 86400, "heures": 3600}
PERIODES = {"jour": ("jours", "chargés", "chacun"), "mois": ("mois", "chargés", "chacun"),
            "année": ("années", "chargées", "chacune")}
PART_CONCENTRATION = 0.8
PART_FAIBLE_PERIODE = 0.01
PART_GROUPE_LOURD = 0.3


def sections_possibles(roles):
    """Analyses proposées selon les types de colonnes : il en faut au moins un de chaque sorte."""
    types = list(roles.values())
    return {"comparer": "Catégorie" in types, "delai": types.count("Date") >= 2, "evolution": "Date" in types}


def une_ligne_par(data, identifiant):
    """Une ligne par valeur de l'identifiant (la dernière du fichier) ; sans identifiant, toutes les lignes."""
    if identifiant is None:
        return data
    return data.loc[data[identifiant].notna()].drop_duplicates(identifiant, keep="last")


def unite_comptee(identifiant):
    return f"{identifiant} distincts" if identifiant else "lignes"


def de(mot):
    """« de lignes », « d'id distincts » : élision devant une voyelle ou un h (noms de colonnes libres)."""
    return f"d'{mot}" if mot[:1].lower() in "aeiouyhéèêàâîôû" else f"de {mot}"


def _groupes(serie):
    return serie.astype("string").fillna(LIBELLE_MANQUANT)


def _nombre(valeur):
    return nombre_lisible(round(float(valeur), 2))


def _fois(rapport):
    """98,38 → « 98 », 2,46 → « 2,5 »."""
    return nombre_lisible(round(rapport)) if rapport >= 10 else nombre_lisible(round(rapport, 1))


def duree_lisible(valeur, unite_temps="jours"):
    """Un délai court passe à l'unité inférieure : 0,0021 jour → « 3 min », 0,92 jour → « 22 h »."""
    heures = valeur * 24 if unite_temps == "jours" else valeur
    if heures < 1:
        return f"{nombre_lisible(round(heures * 60))} min"
    if unite_temps == "heures" or valeur < 1:
        return f"{_nombre(heures)} h"
    return f"{_nombre(valeur)} {'jour' if valeur < 2 else 'jours'}"


def _graphique(tableau, etiquette, autres=False):
    """Les premiers groupes du classement, au format de `classement`.

    Comptage (`autres`) : une ligne « Autres » regroupe le reste ; un petit groupe n'y est pas « fragile ».
    """
    haut = tableau.head(CATEGORIES_GRAPHIQUE)
    lignes = [{"Groupe": str(r.Groupe), "Valeur": float(r.Valeur), "Etiquette": etiquette(r),
               "Type": "manquant" if r.Groupe == LIBELLE_MANQUANT else ("fragile" if r.Fragile and not autres else "valeur")}
              for r in haut.itertuples()]
    reste = tableau.iloc[CATEGORIES_GRAPHIQUE:]
    if autres and len(reste):
        lignes.append({"Groupe": f"Autres ({len(reste)} groupes)", "Valeur": float(reste["Valeur"].sum()),
                       "Etiquette": nombre_lisible(int(reste["Valeur"].sum())), "Type": "autres"})
    return pd.DataFrame(lignes, columns=["Groupe", "Valeur", "Etiquette", "Type"])


def _petits_groupes(reels, unite):
    petits = int((reels["Effectif"] < GROUPE_MIN_COMPARAISON).sum())
    if not petits:
        return []
    return [f"{petits} groupes sur {len(reels)} ont moins de {GROUPE_MIN_COMPARAISON} {unite} : trop peu pour comparer."
            if petits > 1 else f"1 groupe sur {len(reels)} a moins de {GROUPE_MIN_COMPARAISON} {unite} : trop peu pour comparer."]


def _constats_nombre(tableau, groupe, unite):
    total = int(tableau["Effectif"].sum())
    reels = tableau.loc[tableau["Groupe"] != LIBELLE_MANQUANT]
    constats = []
    if len(reels):
        haut = reels.iloc[0]
        phrase = (f"« {haut.Groupe} » compte {nombre_lisible(int(haut.Effectif))} {unite} "
                  f"({part_lisible(haut.Effectif / total)} du total)")
        mediane = float(reels["Effectif"].median())
        if len(reels) >= 3 and mediane > 0 and haut.Effectif / mediane >= 2:
            phrase += f", soit {_fois(haut.Effectif / mediane)} fois la médiane des groupes ({_nombre(mediane)})"
        constats.append(phrase + ".")
    parts = tableau["Effectif"].cumsum() / total
    k = int((parts < 0.5).sum()) + 1
    if len(tableau) >= 5 and k <= len(tableau) * 0.2:
        dont = f", dont « {LIBELLE_MANQUANT} »," if LIBELLE_MANQUANT in tableau["Groupe"].head(k).tolist() else ""
        constats.append(f"{pluriel(k, 'groupe', 'groupes')}{dont} {'concentre' if k == 1 else 'concentrent'} "
                        f"la moitié des {unite}.")
    manquants = tableau.loc[tableau["Groupe"] == LIBELLE_MANQUANT, "Effectif"]
    if len(manquants):
        n = int(manquants.iloc[0])
        constats.append(f"{nombre_lisible(n)} {unite} ({part_lisible(n / total)}) n'ont pas de valeur dans {groupe}.")
    return constats + _petits_groupes(reels, unite)


def _constats_statistique(tableau, ensemble, statistique, mesure, unite):
    comparables = tableau.loc[~tableau["Fragile"] & (tableau["Groupe"] != LIBELLE_MANQUANT)]
    libelle = STATISTIQUES[statistique].lower()
    constats = []
    if len(comparables) >= 2:
        haut, bas = comparables.iloc[0], comparables.iloc[-1]
        constats.append(f"« {haut.Groupe} » : {libelle} de {mesure} {_nombre(haut.Valeur)}, contre {_nombre(ensemble)} "
                        f"pour l'ensemble ({nombre_lisible(int(haut.Effectif))} valeurs).")
        constats.append(f"La plus basse : « {bas.Groupe} » ({_nombre(bas.Valeur)}, {nombre_lisible(int(bas.Effectif))} valeurs).")
    return constats + _petits_groupes(tableau.loc[tableau["Groupe"] != LIBELLE_MANQUANT], unite)


def comparer(data, groupe, statistique="nombre", mesure=None, unite="lignes"):
    """Classement des groupes : effectif, ou moyenne / médiane d'un nombre. Retourne {tableau, graphique, constats}."""
    groupes = _groupes(data[groupe])
    if statistique == "nombre":
        effectifs = groupes.value_counts()
        tableau = pd.DataFrame({"Groupe": effectifs.index.astype(str), "Valeur": effectifs.to_numpy(),
                                "Effectif": effectifs.to_numpy()})
    else:
        resume = data[mesure].groupby(groupes).agg(["mean", "median", "count"])
        resume = resume.loc[resume["count"] > 0]
        tableau = pd.DataFrame({"Groupe": resume.index.astype(str),
                                "Valeur": resume["mean" if statistique == "moyenne" else "median"].to_numpy(),
                                "Effectif": resume["count"].to_numpy()}).sort_values("Valeur", ascending=False)
    tableau = tableau.reset_index(drop=True)
    tableau["Part"] = tableau["Effectif"] / tableau["Effectif"].sum() if len(tableau) else []
    tableau["Fragile"] = tableau["Effectif"] < GROUPE_MIN_COMPARAISON
    if not len(tableau):
        return {"tableau": tableau, "graphique": None, "constats": [f"Aucune valeur à comparer dans {mesure or groupe}."]}
    if statistique == "nombre":
        return {"tableau": tableau, "constats": _constats_nombre(tableau, groupe, unite),
                "graphique": _graphique(tableau, lambda r: nombre_lisible(int(r.Valeur)), autres=True)}
    ensemble = data[mesure].mean() if statistique == "moyenne" else data[mesure].median()
    return {"tableau": tableau, "constats": _constats_statistique(tableau, ensemble, statistique, mesure, unite),
            "graphique": _graphique(tableau, lambda r: f"{_nombre(r.Valeur)} · {nombre_lisible(int(r.Effectif))} val.")}


def duree(data, debut, fin, unite="jours"):
    """Fin − début dans l'unité choisie ; une fin avant le début reste visible (valeur négative)."""
    return (data[fin] - data[debut]).dt.total_seconds() / UNITES_DELAI[unite]


def _poids(comparables, mediane, calculables, unite):
    """Un groupe très lourd peut à lui seul tirer la médiane générale."""
    au_dessus = int((comparables["Valeur"] > mediane).sum())
    lourd = comparables.loc[comparables["Effectif"].idxmax()]
    part = lourd.Effectif / calculables
    ratio = au_dessus / len(comparables)
    if part >= PART_GROUPE_LOURD and ((ratio >= 0.7 and lourd.Valeur < mediane) or (ratio <= 0.3 and lourd.Valeur > mediane)):
        sens = "bas" if lourd.Valeur < mediane else "haut"
        return [f"« {lourd.Groupe} », qui pèse {part_lisible(part)} des {unite}, tire la médiane générale vers le {sens}."]
    return []


def delais(data, debut, fin, groupe=None, unite_temps="jours", unite="lignes"):
    """Délai médian, global et par groupe. Retourne {duree, mediane, calculables, total, tableau, graphique, constats}."""
    valeurs = duree(data, debut, fin, unite_temps)
    negatifs = int((valeurs < 0).sum())
    valides = valeurs.where(valeurs >= 0)
    calculables = int(valides.notna().sum())
    resultat = {"duree": valeurs, "mediane": valides.median() if calculables else None, "calculables": calculables,
                "total": len(data), "tableau": None, "graphique": None, "constats": []}
    constats = resultat["constats"]
    if negatifs:
        constats.append(f"{nombre_lisible(negatifs)} {unite} ont une date de fin avant la date de début : ignorés.")
    sans_date = len(data) - calculables - negatifs
    if sans_date:
        constats.append(f"{nombre_lisible(sans_date)} {unite} sans {debut} ou sans {fin} lisible : ignorés.")
    if not calculables or groupe is None:
        return resultat
    resume = valides.groupby(_groupes(data[groupe])).agg(["median", "count"])
    resume = resume.loc[resume["count"] > 0]
    tableau = pd.DataFrame({"Groupe": resume.index.astype(str), "Valeur": resume["median"].to_numpy(),
                            "Effectif": resume["count"].to_numpy()}).sort_values("Valeur", ascending=False).reset_index(drop=True)
    tableau["Fragile"] = tableau["Effectif"] < GROUPE_MIN_COMPARAISON
    mediane = resultat["mediane"]
    comparables = tableau.loc[~tableau["Fragile"] & (tableau["Groupe"] != LIBELLE_MANQUANT)].reset_index(drop=True)
    if len(comparables) >= 2:
        haut, bas = comparables.iloc[0], comparables.iloc[-1]
        constats.append(f"« {haut.Groupe} » : délai médian {duree_lisible(haut.Valeur, unite_temps)}, contre "
                        f"{duree_lisible(mediane, unite_temps)} pour l'ensemble ({nombre_lisible(int(haut.Effectif))} {unite}).")
        constats.append(f"Le plus court : « {bas.Groupe} », {duree_lisible(bas.Valeur, unite_temps)} "
                        f"({nombre_lisible(int(bas.Effectif))} {unite}).")
        au_dessus = int((comparables["Valeur"] > mediane).sum())
        constats.append(f"{au_dessus} groupes sur {len(comparables)} sont au-dessus du délai médian général.")
        constats += _poids(comparables, mediane, calculables, unite)
    constats += _petits_groupes(tableau.loc[tableau["Groupe"] != LIBELLE_MANQUANT], unite)
    # Le classement montre les plus longs, et le plus court comparable s'il n'y figure pas.
    montres = comparables.head(CATEGORIES_GRAPHIQUE)
    if len(comparables) > CATEGORIES_GRAPHIQUE:
        montres = pd.concat([montres, comparables.tail(1)])
    resultat["tableau"] = tableau
    resultat["graphique"] = pd.DataFrame({
        "Groupe": [f"{g} · {nombre_lisible(int(n))}" for g, n in zip(montres["Groupe"], montres["Effectif"])],
        "Valeur": montres["Valeur"].astype(float).to_numpy(),
        "Etiquette": [duree_lisible(v, unite_temps) for v in montres["Valeur"]],
        "Type": "valeur"})
    return resultat


def evolution(data, date, groupe=None, valeur=None, unite="lignes"):
    """Nombre par période (jour, mois ou année selon l'étendue), pour tous ou pour une valeur d'un groupe."""
    if groupe is not None and valeur is not None:
        data = data.loc[_groupes(data[groupe]) == valeur]
    donnees, periode = compter_par_periode(data[date])
    if periode is None:
        return None
    total = int(donnees["Lignes"].sum())
    pluriel_periode, chargees, chacune = PERIODES[periode]
    pic = donnees.loc[donnees["Lignes"].idxmax()]
    constats = [f"{str(pic['Période'])[:1].upper()}{str(pic['Période'])[1:]} compte le plus {de(unite)} "
                f"({nombre_lisible(int(pic['Lignes']))})."]
    if len(donnees) >= 6:
        trois = donnees.nlargest(3, "Lignes")
        part = trois["Lignes"].sum() / total
        if part >= PART_CONCENTRATION:
            constats.append(f"Les 3 {pluriel_periode} les plus {chargees} ({', '.join(trois['Période'])}) "
                            f"regroupent {part_lisible(part)} des {unite}.")
        faibles = int((donnees["Lignes"] < PART_FAIBLE_PERIODE * total).sum())
        if faibles:
            debut = (f"{faibles} {pluriel_periode} comptent {chacune}" if faibles > 1
                     else f"1 {periode} compte")
            constats.append(f"{debut} moins de 1 % des {unite} : vérifiez si les données couvrent toute la période.")
    sans_date = int(data[date].isna().sum())
    if sans_date:
        constats.append(f"{nombre_lisible(sans_date)} {unite} sans {date} lisible ne sont pas comptés.")
    return {"donnees": donnees, "unite": periode, "constats": constats}
