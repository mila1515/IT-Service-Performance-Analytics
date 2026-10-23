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
# Trio vérifié (contraste sur fond blanc, daltonisme) ; le gris clair reste lisible car chaque barre est libellée.
COULEUR_PRINCIPALE = "#0F8B8D"
COULEUR_FRAGILE = "#62B2B4"
COULEUR_MANQUANT = "#B4BAC2"
LIBELLE_MANQUANT = "Non renseignée"
