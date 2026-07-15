# Architecture du projet

Le projet suit un workflow classique d'analyse de données.

```text
Données sources
    |
    v
Préparation et nettoyage
    |
    v
Analyse exploratoire
    |
    v
Table analytique unique (`incident_clean.csv`)
    |                         |
    v                         v
Analyse SQL              Dashboard Power BI
                         Mesures DAX dynamiques
```

## Rôle des dossiers

- `data/raw` : fichier CSV source.
- `data/processed` : table analytique nettoyée `incident_clean.csv`, utilisée par les notebooks et Power BI.
- `data/database` : base SQLite créée pour les requêtes SQL.
- `notebooks` : étapes du workflow analytique.
- `docs` : documentation métier et technique du projet.

Les requêtes SQL servent à contrôler et approfondir les résultats, sans produire de fichiers de synthèse nécessaires au dashboard. Power BI calcule directement les KPI depuis la table analytique avec DAX, ce qui garantit que les cartes et graphiques réagissent aux filtres.
