# IT Incident Management Analytics

![Python](https://img.shields.io/badge/Python-3.12-blue)
![SQL](https://img.shields.io/badge/SQL-Analytics-lightgrey)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-150458)
![Power BI](https://img.shields.io/badge/Power%20BI-Ready-F2C811)

Projet d'analyse de données de bout en bout combinant **Python**, **SQL**, **Power BI** et **DAX** afin d'analyser la performance du traitement des incidents IT.

Le projet transforme un journal d'incidents ITSM en KPI opérationnels, analyses structurées, recommandations métier et tableau de bord interactif pour aider les responsables IT à suivre la qualité de service, détecter les risques de non-respect SLA et prioriser les actions d'amélioration.

## Résultats clés

| Indicateur | Résultat | Lecture métier |
| --- | ---: | --- |
| Incidents analysés | 24 918 | Base suffisamment large pour suivre la performance du support IT |
| Conformité SLA globale | 63,45 % | Niveau perfectible, avec un risque réel de non-respect des engagements |
| Temps moyen de résolution | 178,17 h | Les délais moyens restent élevés et doivent être suivis par priorité et groupe |
| SLA Critical / High | 2,22 % / 0,98 % | Les incidents les plus sensibles sont les plus à risque |
| Réassignations | 266 h vs 95 h | Les incidents réassignés prennent beaucoup plus de temps à résoudre |

## Aperçu Dashboard

Le dashboard Power BI utilise directement `data/processed/incident_clean.csv`, la table analytique contenant une ligne par incident. Les KPI sont calculés dans Power BI avec des mesures DAX afin de rester dynamiques et de réagir aux segments (`priority`, `assignment_group`, `category` et `opened_month`). Un aperçu statique du dashboard est fourni pour montrer le rendu attendu.

![IT Service Performance Power BI Dashboard](docs/images/powerbi_dashboard.png)

Vues recommandées pour Power BI :

- Cartes KPI : incidents, SLA, temps moyen de résolution, temps moyen de clôture.
- Volume mensuel des incidents.
- Conformité SLA par priorité.
- Performance par groupe support.
- Impact des réassignations sur le temps de résolution.

Mesures DAX principales :

```DAX
Total Incidents =
DISTINCTCOUNT(incident_clean[number])

SLA Compliance % =
DIVIDE(SUM(incident_clean[sla_compliant]), [Total Incidents], 0)

Average Resolution Hours =
AVERAGE(incident_clean[resolution_time_hours])

Average Closure Hours =
AVERAGE(incident_clean[closure_time_hours])

Reassigned Incidents =
CALCULATE([Total Incidents], incident_clean[reassignment_count] > 0)

Reassignment Rate % =
DIVIDE([Reassigned Incidents], [Total Incidents], 0)
```

Les anciens fichiers de synthèse `sql_*.csv` ne sont plus nécessaires pour le dashboard. Les requêtes SQL restent disponibles dans le notebook d'analyse pour valider les résultats sans créer de sources Power BI supplémentaires.

## Problématique métier

Les équipes support IT traitent un volume important d'incidents, répartis par priorité, catégorie et groupe d'affectation. Sans analyse structurée, il devient difficile d'identifier les risques de non-respect des SLA, les groupes support surchargés et les problèmes opérationnels récurrents.

Ce projet répond aux questions suivantes :

- Les incidents sont-ils résolus dans les délais attendus ?
- Quels groupes support concentrent la charge opérationnelle la plus élevée ?
- Quels facteurs sont associés à des délais de résolution plus longs ?
- Peut-on construire un premier modèle simple pour détecter les incidents à risque SLA ?

## Source des données

Le projet utilise un journal d'événements d'incidents ITSM nommé `incident_event_log.csv`. Les données sont anonymisées : les utilisateurs, groupes, lieux et catégories sont remplacés par des identifiants génériques comme `Caller 2403`, `Group 70`, `Location 143` ou `Category 55`.

Plus de détails : [docs/Dataset_Source.md](docs/Dataset_Source.md).

## Déroulé analytique

1. **Compréhension des données**
   Exploration du fichier source, des champs disponibles, des valeurs manquantes, des doublons métier et de la période couverte.

2. **Nettoyage des données**
   Conversion des dates, traitement des valeurs manquantes utiles, création d'une table analytique avec une seule ligne par incident.

3. **Analyse exploratoire**
   Analyse du volume, du SLA, des priorités, des groupes support et de l'effet des réassignations.

4. **Analyse SQL**
   Création d'une base SQLite et validation des KPI avec des requêtes SQL.

5. **Synthèse métier**
   Traduction des résultats en recommandations opérationnelles.

6. **Tableau de bord Power BI**
   Création d'un dashboard interactif alimenté par `incident_clean.csv` et des mesures DAX dynamiques.

## KPI suivis

- Nombre total d'incidents.
- Taux de conformité SLA.
- Temps moyen de résolution.
- Temps moyen de clôture.
- Nombre moyen de réassignations.
- Nombre moyen de réouvertures.
- Volume d'incidents par mois.
- Performance SLA par priorité.
- Charge et performance par groupe support.

## Technologies utilisées

| Catégorie | Technologies |
| --- | --- |
| Programmation | Python |
| Analyse de données | Pandas, NumPy |
| Base de données | SQLite |
| Requêtes | SQL |
| Visualisation | Matplotlib |
| BI / Tableau de bord | Power BI, mesures DAX |
| Environnement | Jupyter Notebook |
| Versioning | Git |

## Structure du dépôt

```text
IT-Service-Performance-Analytics/
|
|-- data/
|   |-- raw/          données sources des incidents
|   |-- processed/    table analytique `incident_clean.csv`
|   `-- database/     base SQLite générée pour l'analyse SQL
|
|-- docs/
|   |-- images/       aperçu dashboard
|   `-- *.md          documentation métier et technique
|
|-- notebooks/        déroulé analytique de bout en bout
|-- powerbi/          projet PBIP, rapport et modèle sémantique
|-- requirements.txt  dépendances Python pinnées
`-- README.md         présentation du projet
```

## Notebooks

1. `01_Data_Understanding.ipynb` - exploration initiale des données.
2. `02_Data_Cleaning.ipynb` - nettoyage et préparation de la table incident.
3. `03_Exploratory_Data_Analysis.ipynb` - analyse des KPI et visualisations.
4. `04_SQL_Analysis.ipynb` - requêtes KPI SQL pour contrôler les résultats.
5. `05_Business_Insights.ipynb` - KPI calculés depuis la table incident, enseignements métier et recommandations.

## Lancer le projet

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
jupyter notebook
```

Pour exécuter tous les notebooks :

```powershell
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
```
