"""Étape 4 : pistes de lecture du rapport, calculées à partir des chiffres seulement.

Entrées : fiches des colonnes (`resume_colonnes`), répétitions des identifiants (`variations`),
résultat des corrections. Sortie : une liste de phrases. Aucune règle métier : chaque phrase dit
ce que les chiffres montrent et propose une précaution de lecture, à vérifier par l'utilisateur.
"""
from src.core.texte import nombre_lisible, pluriel
from src.etape2_comprendre.repetitions import part_lisible

# Seuils statistiques généraux, affichés dans le rapport avec chaque phrase.
PART_PEU_REMPLIE = 0.5
ECART_MOYENNE_MEDIANE = 0.5
PART_DOMINANTE = 0.5
PART_ECARTEES = 0.05


def _remplissage(fiche):
    part = fiche["remplies"] / fiche["total"] if fiche["total"] else 1
    if part < PART_PEU_REMPLIE:
        return (f"{fiche['colonne']} n'est remplie que pour {part_lisible(part)} des lignes : peu utilisable pour "
                "l'analyse telle quelle (à compléter à la source, ou à laisser de côté).")
    return None


def _mesure(fiche):
    if fiche["role"] != "Mesure" or not fiche.get("nombres"):
        return None
    moyenne, mediane = fiche["moyenne"], fiche["mediane"]
    if mediane == 0 and moyenne != 0:
        return (f"{fiche['colonne']} : au moins la moitié des valeurs valent 0 (médiane 0, moyenne "
                f"{nombre_lisible(moyenne)}). La moyenne décrit surtout les quelques valeurs non nulles.")
    if mediane and abs(moyenne - mediane) / abs(mediane) > ECART_MOYENNE_MEDIANE:
        return (f"{fiche['colonne']} : la moyenne ({nombre_lisible(moyenne)}) est loin de la médiane "
                f"({nombre_lisible(mediane)}). Quelques valeurs très grandes ou très petites tirent la moyenne : "
                "la médiane décrit mieux une valeur typique.")
    return None


def _categorie(fiche):
    if fiche["role"] != "Catégorie" or not fiche.get("frequences") or not fiche["remplies"]:
        return None
    valeur, effectif = fiche["frequences"][0]
    part = effectif / fiche["remplies"]
    if part > PART_DOMINANTE:
        return (f"{fiche['colonne']} : « {valeur} » représente {part_lisible(part)} des lignes remplies. "
                "Les comparaisons entre valeurs reposeront surtout sur celle-ci.")
    return None


def _repetition(fiche, resultat):
    if resultat is None:
        return None
    colonne = fiche["colonne"]
    if not resultat["changent"]:
        return (f"{colonne} : les lignes qui partagent une même valeur sont des copies identiques "
                "(voir les lignes identiques dans les décisions).")
    premiere, part = resultat["changent"][0]
    return (f"{colonne} : une même valeur revient sur plusieurs lignes qui ne sont pas identiques "
            f"({premiere} change dans {part_lisible(part)} des groupes). Pour compter les {colonne}, comptez les "
            f"valeurs distinctes ({nombre_lisible(fiche['distinctes'])}) plutôt que les lignes "
            f"({nombre_lisible(fiche['total'])}).")


def _dates(fiche):
    if fiche["role"] == "Date" and fiche.get("illisibles"):
        return (f"{fiche['colonne']} : {pluriel(fiche['illisibles'], 'date illisible', 'dates illisibles')}, "
                "ignorées dans les graphiques dans le temps.")
    return None


def interpretations(fiches, repetitions, resultat):
    """Pistes de lecture, dans l'ordre des colonnes, puis sur l'ensemble des lignes.

    `repetitions` : colonne → résultat de `variations` (identifiants qui se répètent seulement).
    """
    phrases = []
    for fiche in fiches:
        for phrase in (_remplissage(fiche), _mesure(fiche), _categorie(fiche),
                       _repetition(fiche, repetitions.get(fiche["colonne"])), _dates(fiche)):
            if phrase:
                phrases.append(phrase)
    if resultat["total"] and resultat["ecartees"] / resultat["total"] > PART_ECARTEES:
        phrases.append(f"{part_lisible(resultat['ecartees'] / resultat['total'])} des lignes ont été écartées : "
                       "les chiffres peuvent ne plus représenter tout le fichier.")
    return phrases
