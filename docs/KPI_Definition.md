# Définition des KPI

Les KPI sont calculés à partir de la table `incident_clean.csv`, qui contient une ligne par incident et représente le dernier état connu de chaque incident.

Dans Power BI, ces indicateurs sont implémentés avec des mesures DAX calculées directement sur cette table. Aucun fichier de synthèse `sql_*.csv` n'est requis ; les mesures restent ainsi sensibles au contexte de filtre du dashboard.

## Nombre d'incidents

Nombre total d'incidents uniques présents dans la table préparée.

```DAX
Total Incidents = DISTINCTCOUNT(incident_clean[number])
```

## Taux de conformité SLA

Part des incidents résolus dans le respect du SLA.

```text
Incidents conformes SLA / Total incidents
```

```DAX
SLA Compliance % =
DIVIDE(SUM(incident_clean[sla_compliant]), [Total Incidents], 0)
```

## Temps moyen de résolution

Durée moyenne entre l'ouverture de l'incident (`opened_at`) et sa résolution (`resolved_at`).

```DAX
Average Resolution Hours =
AVERAGE(incident_clean[resolution_time_hours])
```

## Temps moyen de clôture

Durée moyenne entre l'ouverture de l'incident (`opened_at`) et sa clôture (`closed_at`).

```DAX
Average Closure Hours =
AVERAGE(incident_clean[closure_time_hours])
```

## Nombre moyen de réassignations

Nombre moyen de réassignations par incident.

```text
Total des réassignations / Total incidents
```

## Nombre moyen de réouvertures

Nombre moyen de réouvertures par incident.

```text
Total des réouvertures / Total incidents
```

## Taux de réassignation complémentaire

Part des incidents ayant été réassignés au moins une fois.

```text
Incidents réassignés / Total incidents
```

Ce taux peut être utilisé en complément du nombre moyen pour distinguer la fréquence du problème de son intensité.

```DAX
Reassigned Incidents =
CALCULATE([Total Incidents], incident_clean[reassignment_count] > 0)

Reassignment Rate % =
DIVIDE([Reassigned Incidents], [Total Incidents], 0)
```

## Taux de réouverture complémentaire

Part des incidents rouverts au moins une fois après leur traitement initial.

```text
Incidents rouverts / Total incidents
```

Comme pour les réassignations, ce taux complète le nombre moyen de réouvertures.
