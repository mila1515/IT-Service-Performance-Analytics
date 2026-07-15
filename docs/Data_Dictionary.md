# Dictionnaire des données

| Colonne | Description métier |
| --- | --- |
| `number` | Identifiant unique de l'incident |
| `opened_at` | Date d'ouverture de l'incident |
| `resolved_at` | Date de résolution |
| `closed_at` | Date de clôture |
| `made_sla` | Indicateur de respect du SLA |
| `priority` | Niveau de priorité de l'incident |
| `impact` | Impact métier déclaré |
| `urgency` | Niveau d'urgence |
| `category` | Catégorie de l'incident |
| `assignment_group` | Groupe support responsable du traitement |
| `reassignment_count` | Nombre de réassignations |
| `reopen_count` | Nombre de réouvertures |

## Colonnes dérivées utilisées dans l'analyse

| Colonne | Description métier |
| --- | --- |
| `resolution_time_hours` | Durée entre l'ouverture et la résolution de l'incident, en heures |
| `closure_time_hours` | Durée entre l'ouverture et la clôture de l'incident, en heures |
| `sla_compliant` | Version numérique de `made_sla`, utilisée pour calculer le taux de conformité SLA |
| `has_reassignment` | Indique si l'incident a été réassigné au moins une fois |
| `has_reopen` | Indique si l'incident a été rouvert au moins une fois |
| `opened_month` | Mois d'ouverture de l'incident, utilisé pour l'analyse mensuelle |
| `priority_level` | Niveau numérique extrait de la priorité |
| `impact_level` | Niveau numérique extrait de l'impact |
| `urgency_level` | Niveau numérique extrait de l'urgence |

Ces colonnes constituent le périmètre principal de l'analyse. Les autres champs du fichier source sont conservés dans les données nettoyées lorsque leur présence peut être utile pour des analyses complémentaires.

## Utilisation dans Power BI

`incident_clean.csv` est l'unique source de données du dashboard. Les champs catégoriels alimentent les segments et les axes, tandis que les champs numériques alimentent les mesures DAX.

Avant le chargement, `resolution_time_hours` et `closure_time_hours` doivent être définis comme nombres décimaux, et `opened_at`, `resolved_at` et `closed_at` comme dates/heures. Si Power BI interprète les décimales comme du texte, utiliser le type **Nombre décimal** avec les paramètres régionaux **Anglais (États-Unis)**, car le fichier CSV emploie le point comme séparateur décimal.
