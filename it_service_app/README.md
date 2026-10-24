# IT Service Performance — application Streamlit

Importer un CSV d'incidents ServiceNow, contrôler les données et explorer la performance du service IT
**sans exécuter le notebook**. L'application reprend les règles de `notebooks/02_Data_Cleaning.ipynb`
et les définitions des KPI du notebook 03/05 et du rapport Power BI.

| Support | Rôle |
|---|---|
| Notebooks | Documenter la préparation des données et les calculs |
| Power BI | Consulter le tableau de bord sur `data/processed/incident_clean.csv` |
| Cette application | Refaire l'analyse sur un nouveau fichier : import, contrôles, filtres, KPI, exports |

L'application est indépendante : elle n'importe rien de `src/` (application d'audit qualité) et ne modifie
ni les notebooks, ni Power BI, ni `data/`.

## Lancement

Depuis la racine du dépôt :

```bash
pip install -r it_service_app/requirements.txt   # si besoin, dans un environnement virtuel
python -m streamlit run it_service_app/app.py
```

L'application s'ouvre sur **http://localhost:8510** (port défini dans `it_service_app/.streamlit/config.toml`).
Ce port évite la plage 8501-8503, déjà prise sur le poste de développement et où Streamlit se décale
automatiquement quand un port est occupé. S'il est pris, forcer un autre port :
`python -m streamlit run it_service_app/app.py --server.port 8520`.

Le fichier importé reste en mémoire de session : rien n'est enregistré.

### Avec Docker

Depuis la racine du dépôt :

```bash
docker compose -f it_service_app/compose.yaml up -d --build   # construire et démarrer
docker compose -f it_service_app/compose.yaml logs -f         # suivre les journaux
docker compose -f it_service_app/compose.yaml down            # arrêter
```

L'application est servie sur **http://localhost:8510**, accessible depuis ce poste seulement (`127.0.0.1`).
Autre port côté poste : `IT_SERVICE_PORT=8520 docker compose -f it_service_app/compose.yaml up -d`.

- Image `python:3.12-slim`, exécutée avec un utilisateur sans droits d'administration (`analyst`).
- L'image ne contient que le code et `.streamlit/` : ni les données, ni les tests, ni le reste du dépôt.
- Aucun volume : les fichiers importés restent en mémoire et disparaissent à l'arrêt du conteneur.
- Un contrôle de santé interroge `/_stcore/health` toutes les 15 s ; `restart: unless-stopped` relance l'application après un redémarrage de Docker.
- Projet Compose `it-service-performance`, distinct de celui de l'application d'audit (`analyse-csv`, port 8503).

Tests : `python -m unittest discover -s it_service_app/tests`

## Parcours

1. **Importer** un CSV : le journal brut (`data/raw/incident_event_log.csv`, plusieurs lignes par incident)
   ou une table d'incidents (`data/processed/incident_clean.csv`, une ligne par incident).
2. **Vérifier** : lignes, colonnes, incidents uniques, format détecté, formats de dates, colonnes absentes,
   le tableau des anomalies et exclusions qui influencent les calculs, et les **options de nettoyage facultatives**.
3. **Filtrer** : période (sur la date d'ouverture `opened_at`), priorité, catégorie, état, équipe.
4. **Indicateurs et graphiques**, tous calculés sur la sélection filtrée.
5. **Télécharger** le rapport d'analyse (Word), les données nettoyées, les données filtrées et les indicateurs.

### Interface

- **Logo** `assets/logo.svg` : jauge de performance et ligne de supervision, aussi utilisé comme icône d'onglet.
- **Thème** (`.streamlit/config.toml`) : bleu nuit `#1E40AF` pour les actions et les graphiques, turquoise `#0F766E`
  en accent, fond gris-bleu `#F3F6FA` et cartes blanches, police Inter, titres sobres (`headingFontSizes`).
- **Graphiques** : une couleur par série ; les valeurs de remplacement (« Inconnu », « Autres ») sont en gris pour ne
  pas être confondues avec de vraies équipes ou catégories. Graduations et tableaux au format français (24 918 · 1,85).

## Colonnes attendues

Format ServiceNow du projet (séparateur `,` ou `;`, UTF-8 ou Windows-1252, `?` = valeur manquante).

| Colonne | Obligatoire | Utilisation |
|---|---|---|
| `number` | oui | identifiant de l'incident |
| `opened_at` | oui | date d'ouverture, filtre de période, délais |
| `sys_updated_at` | si journal | choix du dernier état de chaque incident |
| `sys_mod_count` | non | départage des événements ex-aequo |
| `incident_state` | non | incidents ouverts / résolus, délai de clôture |
| `resolved_at`, `closed_at` | non | délais de résolution et de clôture |
| `made_sla` | non | respect des SLA |
| `reassignment_count`, `reopen_count` | non | réassignations, réouvertures |
| `priority`, `category`, `assignment_group` | non | filtres et répartitions |

Dates acceptées : `jj/mm/aaaa hh:mm` (fichier brut) et `aaaa-mm-jj hh:mm:ss` (exports pandas), pour chaque colonne
le format qui en lit le plus. Une date illisible devient manquante et est comptée dans les contrôles.
Si une colonne utile manque, seuls les indicateurs concernés sont indisponibles, avec la raison affichée.

## Préparation (règles du notebook 02)

- **Événement ou incident** : un journal contient plusieurs lignes par incident ; on garde le **dernier état connu**
  (`sys_updated_at` le plus récent). Les lignes strictement identiques (vrais doublons) sont comptées à part.
- Valeurs manquantes : `category`, `subcategory`, `assignment_group`, `contact_type`, `location` → `Inconnu` ;
  `assigned_to`, `resolved_by`, `opened_by` → `Non assigne`. Chaque remplacement est compté.
- `resolution_time_hours` = `resolved_at − opened_at` et `closure_time_hours` = `closed_at − opened_at`, en heures,
  arrondis à 2 décimales ; une durée négative est exclue.
- `sla_compliant` = `made_sla` (1/0), `has_reassignment` = `reassignment_count > 0`, `has_reopen`, `priority_level`,
  `impact_level`, `urgency_level`, `opened_month`, `opened_hour`.
- Une ligne sans numéro d'incident est exclue (comptée). Aucune autre ligne n'est supprimée.

- **Ex-aequo** : `sys_updated_at` est à la minute près ; à date égale, la ligne au `sys_mod_count` le plus élevé est
  gardée (tri stable). Le notebook 02 applique la même règle depuis sa correction du 24/10/2026.
- **SLA** : un `made_sla` vide ou illisible reste manquant et est exclu du SLA (même règle que le notebook corrigé).

### Options de nettoyage facultatives

Décochées par défaut : les résultats restent ceux des règles ci-dessus, identiques au rapport Power BI.
Une option cochée s'applique à tous les indicateurs, graphiques, exports et au rapport, qui la mentionnent.

| Option | Effet | Incidents concernés (journal brut) |
|---|---|---|
| Exclure les incidents sans équipe | retire les incidents `assignment_group` = « Inconnu » | 2 157 |
| Exclure les incidents sans catégorie | retire les incidents `category` = « Inconnu » | 7 |
| Compter un statut SLA vide comme non conforme | `sla_compliant` vide → 0 (ancienne règle du notebook) | 0 |
| Écarter des délais les résolutions de plus de 30 jours | incident gardé, délai de résolution retiré des moyennes | 1 149 |

### Différences avec le notebook (sans effet sur les données du projet)

Deux protections propres à l'application, pour un nouveau fichier moins propre :

| Cas | Notebook 02 | Application | Effet sur `incident_event_log.csv` |
|---|---|---|---|
| `sys_updated_at` invalide | peut être pris pour le dernier état | jamais retenu comme dernier état | aucun (0 date invalide) |
| Date de clôture sur un incident non `Closed` | délai de clôture calculé | délai de clôture vide | aucun (tous les incidents sont `Closed`) |

## Indicateurs

| KPI | Unité | Définition | Population |
|---|---|---|---|
| Incidents uniques | incidents | numéros `number` distincts | incidents filtrés |
| Incidents résolus / ouverts | incidents | dernier état `Resolved` ou `Closed` / autre | incidents filtrés |
| Délai moyen / médian de résolution | heures | moyenne / médiane de `resolved_at − opened_at` | incidents avec dates d'ouverture et de résolution valides et cohérentes |
| Délai moyen de clôture | heures | moyenne de `closed_at − opened_at` | incidents `Closed` avec dates valides |
| Respect des SLA | % | part des incidents avec `made_sla = True` (notebook et DAX `SLA Compliance %`) | incidents avec statut SLA, **ouverts compris** |
| Respect des SLA (résolus) | % | même calcul | incidents `Resolved`/`Closed` avec statut SLA |
| Taux d'incidents réassignés | % | part avec `reassignment_count > 0` (DAX `Reassignment Rate %`) | incidents avec compteur renseigné |
| Réassignations moyennes | par incident | moyenne de `reassignment_count` (notebook) | incidents avec compteur renseigné |
| Réouvertures moyennes | par incident | moyenne de `reopen_count` | incidents avec compteur renseigné |

- **Pas de SLA sans statut** : sans `made_sla` exploitable, le SLA est déclaré indisponible (aucun objectif en heures n'est supposé).
- **Pas de réassignations déduites des événements** : sans `reassignment_count`, l'indicateur est indisponible.
  `reassignment_count` est un compteur cumulé : sa valeur au dernier état est le total de l'incident.

### Analyses détaillées (reprises des notebooks 03 à 05)

Les ventilations utilisent la même règle que la fonction `summarize` du notebook 05 : incidents uniques, SLA (%)
et délais moyen et médian de résolution par valeur.

| Analyse | Notebook d'origine | Contenu |
|---|---|---|
| Évolution du nombre d'incidents | 03, 04 | incidents par mois d'ouverture |
| Respect des SLA par mois | 04 | SLA par mois d'ouverture (nombre d'incidents en infobulle) |
| Respect des SLA par priorité | 03, 04, 05 | graphique + tableau incidents, SLA, délais |
| Effet des réassignations | 03, 04, 05 | avec / sans réassignation : incidents, SLA, délais |
| Délais de résolution | — | incidents par tranche de délai (< 4 h … > 30 j) |
| Répartition par catégorie | — | 15 catégories les plus fréquentes, le reste en « Autres » |
| Respect des SLA par équipe | 03, 04, 05 | 15 équipes les plus chargées, au moins 20 incidents (seuil du notebook) |
| Incidents les plus longs | 04, 05 | 25 délais de résolution les plus longs |
| Incidents les plus réassignés | — | 20 incidents avec le plus de réassignations |

Ces tableaux redonnent les valeurs des notebooks : SLA Critical 1,85 % et High 0,49 % ;
avec réassignation 11 369 incidents, SLA 45,58 % ; sans réassignation, délai moyen 94,98 h ; Group 70 SLA 83,84 % ;
mars 2016 SLA 39,86 % ; incident le plus long INC0001839 (vérifié par les tests).

### Lecture des résultats

Sous les KPI, l'application rédige quelques messages à partir de la sélection filtrée, dans l'esprit du notebook 05.
Un message n'apparaît que si les données le permettent.

| Message | Règle |
|---|---|
| Taux de respect des SLA | KPI « Respect des SLA » |
| Priorités à surveiller | SLA d'une priorité au moins **10 points** sous le taux global (`ECART_SLA_POINTS`) |
| Équipes | équipe la plus chargée, et SLA le plus bas parmi les 15 équipes les plus chargées (≥ 20 incidents) |
| Effet des réassignations | délai moyen et SLA avec / sans réassignation |
| Moyenne et médiane | signalé si la moyenne dépasse **2 fois** la médiane |
| Tendance mensuelle | nombre de mois sous **1 %** des incidents (`PART_MOIS_FAIBLE`) |

Sur le journal brut, sans filtre : SLA 63,42 % ; Critical 1,85 % et High 0,49 % ; Group 70 la plus chargée
(9 444 incidents, SLA 83,84 %) ; réassignés 266,08 h contre 94,98 h ; médiane 22,10 h contre moyenne 178,17 h ;
10 mois sur 13 sous 1 % des incidents. Ces messages montrent des liens, pas des causes.

### Étape « Vérifier »

Reprend le notebook 01 : lignes, colonnes, incidents uniques, **lignes moyennes par incident**, **période couverte**
(première et dernière `opened_at` valides), format détecté, formats de dates, colonnes absentes, anomalies et
exclusions, et **valeurs manquantes par colonne** du fichier importé (avant réduction au dernier état, `?` compris).

## Exports

| Fichier | Contenu | Format |
|---|---|---|
| `rapport_analyse_incidents_it.docx` | rapport d'analyse imprimable (voir ci-dessous) | Word |
| `it_service_incidents_nettoyes.csv` | données nettoyées : une ligne par incident, toute la période | CSV UTF-8 |
| `it_service_incidents_filtres.csv` | même table, filtres de l'étape 3 appliqués | CSV UTF-8 |
| `it_service_kpi.csv` | indicateurs : valeur, unité, définition, population, filtres et options | CSV UTF-8 avec BOM (Excel) |

Les tables d'incidents ont **les 46 colonnes de `incident_clean.csv`, dans le même ordre** : sans option cochée,
`it_service_incidents_nettoyes.csv` est identique à `incident_clean.csv` et peut remplacer la source du rapport
Power BI. Les noms de fichiers sont différents, donc rien n'est écrasé.

### Rapport d'analyse (Word)

Écrit pour un lecteur non technique, environ 7 pages sur le journal brut (`rapport.py`) :

1. **Le fichier analysé** : ce qu'est un export d'incidents ServiceNow, ce que représente une ligne (événement ou
   incident), chiffres clés et signification des colonnes principales.
2. **Contrôle et nettoyage** : les règles expliquées simplement, ce qui a été trouvé dans le fichier, les options choisies.
3. **Périmètre et indicateurs** : filtres actifs, chaque KPI avec ce qu'il mesure et sur quels incidents.
4. **Analyses** : les graphiques de l'écran (mêmes définitions, `graphiques.py`) avec une légende de lecture, et les
   tableaux par priorité, réassignation et incidents les plus longs.
5. **Interprétation et résumé** : les messages de la lecture des résultats et les limites de l'analyse.

## Vérification (même fichier, même périmètre)

| KPI | Notebooks 03 à 05 | App sur `incident_clean.csv` | App sur le journal brut |
|---|---|---|---|
| Incidents | 24 918 | 24 918 | 24 918 |
| Respect des SLA | 63,42 % | 63,42 % | 63,42 % |
| Délai moyen de résolution | 178,17 h | 178,17 h | 178,17 h |
| Délai médian de résolution | — | 22,10 h | 22,10 h |
| Réassignations moyennes | 0,94 | 0,94 | 0,94 |
| Incidents ouverts | 0 | 0 | 0 |

**Table identique** : préparer le journal brut dans l'application redonne `incident_clean.csv` cellule par cellule
(24 918 incidents × 46 colonnes, aucun écart), vérifié par le test `test_journal_brut_donne_la_table_du_notebook`.

**Historique.** Avant le 24/10/2026, le notebook 02 départageait mal les ex-aequo : pour 35 des 68 incidents concernés,
il gardait un état intermédiaire (28 `Resolved`, 7 `New`) au lieu de l'état `Closed` enregistré dans la même minute
avec un `sys_mod_count` plus élevé, et 7 statuts SLA étaient faux (SLA global 63,45 % au lieu de 63,42 %,
High 0,98 % au lieu de 0,49 %). L'écart a été détecté en comparant l'application au notebook, puis corrigé dans le notebook.

## Limites

- Format ServiceNow uniquement : pas d'écran de correspondance des colonnes ; un fichier avec d'autres noms de colonnes
  est refusé avec la liste des colonnes manquantes.
- Le SLA repose sur le statut `made_sla` fourni par ServiceNow ; aucun objectif par priorité n'est recalculé.
- Les délais sont calendaires (24 h/24, sans heures ouvrées ni jours fériés).
- Le volume est concentré sur mars–mai 2016 : les autres mois contiennent peu d'incidents et ne permettent pas de
  conclure à une tendance.
- Les fichiers très volumineux sont lus en mémoire (journal brut de 46 Mo : environ 10 s de préparation).
