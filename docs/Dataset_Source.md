# Source des données

Le projet utilise un fichier d'incidents ITSM nommé `incident_event_log.csv`.

Le jeu de données est un journal d'événements d'incidents inspiré d'un contexte ServiceNow / ITIL. Les valeurs sont anonymisées : les utilisateurs, groupes, lieux, catégories et identifiants techniques sont remplacés par des libellés génériques comme `Caller 2403`, `Group 70`, `Location 143` ou `Category 55`.

## Périmètre observé

- Journal brut : 141 712 événements.
- Incidents uniques : 24 918 incidents.
- Période d'ouverture : de février 2016 à février 2017.
- Granularité source : plusieurs lignes possibles par incident.
- Granularité analytique : une ligne par incident dans `incident_clean.csv`.

## Remarque importante

La table finale `incident_clean.csv` représente le dernier état connu de chaque incident. Elle est adaptée au calcul des KPI de pilotage, mais elle ne remplace pas le journal complet si l'objectif est d'analyser précisément chaque changement d'état dans le temps.

## Confidentialité

Les données ne contiennent pas de noms réels visibles dans le projet. Les champs sensibles sont pseudonymisés ou remplacés par des identifiants génériques.
