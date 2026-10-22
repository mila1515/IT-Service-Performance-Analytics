"""Formatage des nombres et des pluriels pour les phrases affichées à l'utilisateur (français)."""


def nombre_lisible(valeur):
    """1234 → « 1 234 », 18.1 → « 18,1 », 15.0 → « 15 » (au plus deux décimales)."""
    texte = f"{valeur:,.2f}".rstrip("0").rstrip(".") if isinstance(valeur, float) else f"{valeur:,}"
    return texte.replace(",", " ").replace(".", ",")


def pluriel(n, singulier, forme_plurielle=None):
    """« 1 case », « 3 cases » ; `forme_plurielle` pour les accords irréguliers ou les groupes de mots."""
    return f"{nombre_lisible(n)} {singulier if n <= 1 else (forme_plurielle or singulier + 's')}"
