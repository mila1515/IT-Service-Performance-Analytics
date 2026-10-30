# Assistant IA

Onglet facultatif qui explique le fichier, conseille des corrections et propose des analyses, avec l'API GPT d'OpenAI.
**L'IA propose, l'utilisateur décide** : aucune donnée n'est modifiée et aucun choix n'est coché à sa place.

## Configurer la clé

Créer un fichier `.env` à la racine du dépôt (déjà ignoré par Git et par Docker) :

```text
OPENAI_API_KEY=votre_clé
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` est facultatif. Sans clé, l'onglet explique quoi faire et les étapes 1 à 5 fonctionnent normalement.

## Ce qui est envoyé

- **Envoyé :** nombre de lignes et de colonnes, noms et types des colonnes, remplissage, statistiques (minimum, médiane,
  moyenne, maximum, dates extrêmes), comptages des problèmes et choix possibles.
- **Jamais envoyé :** les lignes du fichier, les valeurs fréquentes ni les exemples des cartes.
- **Noms de colonnes sensibles :** cocher « Masquer les noms de colonnes » pour envoyer « Colonne 1, Colonne 2… ».
- L'écran montre le résumé exact avant l'envoi, et l'IA n'est appelée qu'au clic.

## Où vont les réponses

| Réponse | Où elle apparaît |
|---|---|
| Conseils de correction | sous chaque carte de l'étape 3, et dans le rapport avec la décision prise (suivie ou non) |
| Résumé du fichier, pistes d'analyse | dans l'onglet et dans le rapport |

Sans demande à l'IA, les cartes et le rapport restent identiques. Les réponses sont effacées quand le fichier change.

## Fichiers

| Fichier | Rôle |
|---|---|
| `resume.py` | construit le résumé sans valeurs du fichier, et masque les noms si demandé |
| `client.py` | lit la clé et appelle l'API |
| `conseils.py` | rédige les consignes et contrôle les réponses (seuls les choix de la carte sont acceptés) |
| `ecran.py` | l'onglet, et la suggestion affichée sous une carte |
