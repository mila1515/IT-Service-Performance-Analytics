# IT Service Performance — application Streamlit

[← Retour à la présentation des trois travaux](../README.md)

Cette application permet de refaire l'analyse des incidents IT sur un nouveau fichier, **sans exécuter de notebook** : import d'un CSV ServiceNow, contrôle des données, filtres, indicateurs et exports. Elle reprend les règles de nettoyage et les définitions des KPI des [notebooks](../notebooks/README.md), et reste indépendante du reste du dépôt.

## Le parcours

1. **Importer** un journal brut (plusieurs lignes par incident) ou une table d'incidents (une ligne par incident).
2. **Vérifier** les lignes, les colonnes, les dates et les anomalies, avec des options de nettoyage facultatives.
3. **Filtrer** par période, priorité, catégorie, état ou équipe.
4. **Explorer** les indicateurs et les graphiques.
5. **Télécharger** le rapport Word, les données et les indicateurs.

## Indicateurs

- Nombre d'incidents uniques, résolus et ouverts.
- Délais moyen et médian de résolution, délai moyen de clôture.
- Respect des SLA.
- Taux de réassignation, réassignations et réouvertures moyennes.
- Analyses par mois, priorité, catégorie et équipe, et incidents les plus longs.

## Fiabilité

Sur le journal d'origine, l'application retrouve les résultats des notebooks : 24 918 incidents, 63,42 % de respect des SLA et 178,17 h de délai moyen. Un test vérifie aussi que la table produite est identique à `incident_clean.csv`, cellule par cellule.

## Lancer l'application

Depuis la racine du dépôt :

```bash
pip install -r it_service_app/requirements.txt
python -m streamlit run it_service_app/app.py
```

Ou avec Docker :

```bash
docker compose -f it_service_app/compose.yaml up -d --build
```

L'application s'ouvre sur http://localhost:8510. Le fichier importé reste en mémoire : rien n'est enregistré.

Tests : `python -m unittest discover -s it_service_app/tests`

## Stack

Python · pandas · Streamlit · Altair · python-docx · Docker

## Limites

- Format ServiceNow uniquement : un fichier avec d'autres noms de colonnes est refusé, avec la liste des colonnes manquantes.
- Le SLA repose sur le statut `made_sla` fourni par ServiceNow.
- Les délais sont calendaires, sans heures ouvrées ni jours fériés.
