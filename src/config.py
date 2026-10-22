"""Constantes de l'application : seuils, limites d'affichage et vocabulaire commun.

Un seul endroit pour les valeurs qui reviennent dans plusieurs modules.
"""

# Codes souvent utilisés pour « pas d'information » (comparaison sans tenir compte de la casse).
# Ils restent des valeurs tant que l'utilisateur ne les déclare pas comme manquants.
MARQUEURS_POSSIBLES = frozenset({"?", "na", "n/a", "null", "none", "-", "inconnu"})

# Aperçu et cartes de colonnes.
LIGNES_APERCU = 20
CATEGORIES_RESUME = 5

# Graphiques de contrôle.
CATEGORIES_GRAPHIQUE = 10
CATEGORIES_MAX_POUR_REPARTITION = 30
VALEURS_MIN_MOYENNE = 3
COULEUR_PRINCIPALE = "#1F5FD1"
COULEUR_FRAGILE = "#9DB8EA"
COULEUR_MANQUANT = "#B4BAC4"
LIBELLE_MANQUANT = "Non renseignée"
