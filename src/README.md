# Analyse simple — audit qualité d'un CSV

[← Retour à la présentation des trois travaux](../README.md)

**Analyse simple** est un prototype d'application web qui guide l'utilisateur pour vérifier et préparer n'importe quel fichier CSV avant de l'analyser, sans écrire de code. L'outil ne contient aucune règle métier : il fonctionne aussi bien sur des incidents IT que sur des ventes ou des relevés de capteurs.

## Le parcours

```mermaid
flowchart LR
    F[/Fichier CSV/] --> E1["1 · Importer"]
    E1 --> E2["2 · Comprendre"]
    E2 --> E3["3 · Corriger"]
    E3 --> E4["4 · Visualiser"]
    E4 --> E5["5 · Analyser"]
    E5 --> R[/"Rapport HTML ou Word<br/>Données corrigées"/]
```

| Étape | Ce qu'elle apporte |
| --- | --- |
| 1 · Importer | Lit le fichier et en montre un aperçu. L'original n'est jamais modifié. |
| 2 · Comprendre | Résume chaque colonne et liste les points à vérifier. Rien ne change à cette étape. |
| 3 · Corriger | Propose un choix par problème : codes manquants, texte dans des nombres, cases vides, doublons, dates ambiguës, espaces en trop. Par défaut, rien ne change. |
| 4 · Visualiser | Contrôle en graphiques que les données corrigées sont plausibles. |
| 5 · Analyser | Compare des groupes, mesure un délai, suit une évolution, puis exporte le rapport et les données. |

## Assistant IA (facultatif)

Un onglet explique le fichier, conseille des corrections et propose des analyses avec l'API OpenAI. L'IA n'est appelée qu'au clic, ne reçoit qu'un résumé sans les lignes du fichier et ne modifie aucune donnée. Sans clé, tout le reste fonctionne. Détails : [ia/README.md](ia/README.md).

## Lancer l'outil

Depuis la racine du dépôt :

```powershell
python -m pip install -r src/requirements.txt
python -m streamlit run src/app.py
```

Ou avec Docker, puis ouvrir http://localhost:8503 :

```powershell
docker compose up -d --build
```

## Stack

Python · pandas · Streamlit · Altair · python-docx · API OpenAI · Docker

Tests : `python -m unittest discover -s src/tests`

## Limites du prototype

- Un seul fichier CSV à la fois, jusqu'à 400 Mo : pas de connexion à une base de données.
- Rien n'est sauvegardé : il faut télécharger son travail avant de fermer la page.
- Utilisation sur le poste uniquement, sans authentification.

## Améliorations possibles

- Se connecter aux sources de l'entreprise : bases de données, SharePoint, API.
- Mieux tenir les gros volumes, par exemple avec DuckDB ou Polars.
- Automatiser les contrôles à chaque mise à jour des données.
