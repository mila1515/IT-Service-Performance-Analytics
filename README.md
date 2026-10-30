# Du journal d'incidents à l'audit qualité des données

Ce dépôt réunit trois travaux qui se suivent : une analyse de données, une application qui permet de la refaire sur un nouveau fichier, puis un outil d'audit qualité valable pour n'importe quel CSV.

| Travail | Objectif | En détail |
| --- | --- | --- |
| **1. Analyse de départ** | Évaluer la performance du traitement des incidents IT | [README de l'analyse](notebooks/README.md) |
| **2. IT Service Performance** | Refaire cette analyse sur un nouveau fichier, sans notebook | [README de l'application](it_service_app/README.md) |
| **3. Audit qualité (Analyse simple)** | Vérifier et préparer n'importe quel CSV avant de l'analyser | [README de l'outil](src/README.md) |

## 1. Analyse de départ

**But :** transformer un journal d'incidents ITSM en indicateurs, en recommandations et en tableau de bord.

**Objectif :** aider les responsables IT à suivre le respect des SLA, à repérer les groupes surchargés et à prioriser les améliorations.

**Outils :** Python, pandas, SQL (SQLite), Jupyter Notebook, Power BI et DAX.

[Voir les résultats, les notebooks et le tableau de bord →](notebooks/README.md)

## 2. IT Service Performance

**But :** rendre l'analyse réutilisable dans une application web.

**Objectif :** importer un CSV d'incidents ServiceNow, contrôler les données et explorer les KPI avec des filtres et des exports, sans exécuter de notebook.

**Outils :** Python, pandas, Streamlit, Docker.

[Voir le lancement et le fonctionnement de l'application →](it_service_app/README.md)

## 3. Audit qualité (Analyse simple)

**But :** vérifier la fiabilité d'un fichier avant de s'en servir pour décider, sans écrire de code.

**Objectif :** repérer les problèmes tôt, laisser l'utilisateur décider de chaque correction et garder la trace de ces décisions dans un rapport. Un assistant IA conseille sans rien modifier et ne reçoit qu'un résumé du fichier, jamais ses lignes.

**Outils :** Python, pandas, Streamlit, Altair, API OpenAI, Docker.

Ce travail est un prototype. Cliquez sur l'image pour voir la démonstration (1 min 35, données fictives) :

[![Démonstration vidéo d'Analyse simple]

https://github.com/user-attachments/assets/1210ee9e-5ea5-43ee-803e-3c29d0b87e3d



[Voir le parcours, le lancement et l'assistant IA →](src/README.md)
