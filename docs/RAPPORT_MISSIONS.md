# Rapports des missions — application d'analyse de données (MVP)

Un seul fichier pour tous les rapports, du plus ancien au plus récent. Le cahier des
charges et le tableau de suivi sont dans [MISSIONS_MVP.md](MISSIONS_MVP.md).

## Sommaire

- [Mission 1 — Stabiliser : rapport (aucune correction appliquée)](#mission-1--stabiliser--rapport-aucune-correction-appliquée)
- [Mission 2 — Corrections validées : rapport](#mission-2--corrections-validées--rapport)
- [Mission 3 — Test de charge : rapport](#mission-3--test-de-charge--rapport)
- [Mission 4 — Filtres, caractère générique et nettoyage du code : rapport](#mission-4--filtres-caractère-générique-et-nettoyage-du-code--rapport)
- [Mission 5 — Dashboard : ordre, largeur, modification : rapport](#mission-5--dashboard--ordre-largeur-modification--rapport)
- [Mission 6 — Règles de qualité : rapport](#mission-6--règles-de-qualité--rapport)
- [Mission de nettoyage — Étapes 0 et 1 : état de départ et audit (lecture seule)](#mission-de-nettoyage--étapes-0-et-1--état-de-départ-et-audit-lecture-seule)

---

## Mission 1 — Stabiliser : rapport (aucune correction appliquée)

Date : 2026-10-22 · Branche : `powerbi-updates`

### 1. Ce qui a été fait

| Étape | Résultat |
|---|---|
| Environnement | `.venv` : Python 3.12.7, streamlit 1.66.0, pandas 3.0.3, altair 6.3.0, numpy 2.5.1 (déjà installés, conformes à `src/requirements.txt`) |
| Tests moteur + interface | `python -m unittest discover -s src/tests` (depuis la racine) → **38 tests, OK** |
| Lancement réel | `python -m streamlit run src/app.py` → serveur démarré, `/_stcore/health` = `ok`, aucun avertissement de dépréciation au démarrage |
| Parcours des 6 étapes | Via `streamlit.testing.v1.AppTest` sur `src/tests/fixtures/exemple.csv` → **aucune exception** dans les 6 étapes |
| Sondes ciblées | Points 6 d) du cahier, noms de colonnes spéciaux, nouvel import, temps de calcul sur le CSV réel |

CSV d'exemple créé : [src/tests/fixtures/exemple.csv](../src/tests/fixtures/exemple.csv)
(`id` texte à zéros initiaux, `categorie` avec deux « ? », `montant` avec « abc » et un vide, `date_commande`, un doublon strict).

### 2. Écart important entre le cahier et le code réel

Le cahier (section 3) décrit un état plus ancien que le code :

- pas de fichier `app.py` à la racine ni d'onglets : l'application est `src/app.py`, avec un **parcours en 6 étapes dans la barre latérale** (Découverte, Exploration brute, Nettoyage, Comparaison, Analyse et visualisation, Synthèse et export) ;
- la logique est répartie dans `src/analysis.py`, `quality.py`, `diagnostics.py`, `visualization.py`, `repetitions.py`, `reporting.py` (sans Streamlit) et `*_ui.py`, `dashboard.py` (Streamlit) ;
- les fonctions `agreger()` et `reinitialiser()` **n'existent pas** ; leurs équivalents sont `chart_data()` (`src/visualization.py`) et le bloc de réinitialisation sur `source_id` (`src/app.py`) ;
- **38 tests** (moteur et interface), pas 12 ; commande : `python -m unittest discover -s src/tests` depuis la racine ;
- plusieurs éléments listés comme « pas encore disponibles » **existent déjà** dans le code : filtres globaux et locaux, ordre / ligne / largeur des graphiques, modification d'un graphique, règles qualité avec seuil et P1/P2/P3, diagnostic des répétitions avec clé composée. Ils n'ont pas été audités en profondeur dans cette mission.

### 3. Problèmes constatés

#### Bloquants

| # | Problème | Preuve | Correction proposée |
|---|---|---|---|
| B1 | Une colonne nommée **`Valeur`** rend impossibles les graphiques Barres et Tableau croisé qui l'utilisent (équivalent du point « agreger() / valeur »). | `chart_data()` → `ValueError: cannot insert Valeur, already exists` ; dans l'interface : « Configuration à corriger : cannot insert Valeur… » pour 5 suggestions sur 18. `valeur` (minuscule), `Groupe`, `Série` passent. | Nommer l'index avant `reset_index` (`rename_axis("Groupe")`, `rename_axis(["Groupe", "Série"])`) au lieu de renommer après. Test sur des colonnes `Valeur`, `Groupe`, `Série`. |
| B2 | Une colonne **numérique au rôle « Date »** (ex. année 2023) est convertie silencieusement en **1970-01-01 00:00:00.000002023**, sans être comptée comme invalide. | `prepare(df, {"annee": "Date"})` → dates de 1970, `invalides: {}`. La même année en texte donne bien 2023-01-01. | Dans `prepare()`, ne jamais interpréter un nombre comme un horodatage en nanosecondes : convertir les entiers via leur texte (année `%Y`), sinon compter la valeur comme invalide et l'afficher. Test dédié. |

#### Gênants

| # | Problème | Preuve | Correction proposée |
|---|---|---|---|
| G1 | Étape 4 : « Cellules manquantes » **brut 1 → nettoyé 3** après reconnaissance des « ? » : on croit que le nettoyage a créé des vides. | Le brut est compté avec `raw.isna()`, le nettoyé après normalisation des marqueurs. | Compter le brut sur `normalize_missing(raw, dictionnaire)` et l'indiquer dans le libellé. |
| G2 | Les **identifiants numériques** entrent dans les statistiques descriptives (étapes 2 et 4) et la colonne explorée par défaut est `id` (histogramme, valeurs atypiques sur des identifiants). | Tableau de statistiques = 1 ligne (`id`) sur l'exemple. | Passer les rôles du dictionnaire à `statistics()` / `explore()` et exclure Identifiant et Date des mesures (le rôle reste corrigeable). |
| G3 | Une mesure contenant **une seule valeur non numérique** (`abc`) devient « Catégorie » : pas de moyenne/médiane proposée, « Inconnu » proposé pour `montant`, graphiques en barres par montant. Rien ne signale que la colonne est presque entièrement numérique. | Rôles proposés : `montant → Catégorie (str)` ; choix offerts : Conserver / Supprimer / Inconnu. | Ajouter au diagnostic un constat « colonne majoritairement numérique : N valeurs non convertibles » avec les valeurs en cause, **sans changer le rôle** : l'utilisateur décide de passer le type à Nombre. |
| G4 | Changer une **option de lecture** (séparateur, encodage, décimal, colonnes texte) sur le même fichier **réinitialise toute la session** (dictionnaire, règles, nettoyage, versions, dashboard) sans prévenir. | `source_id` combine contenu et options ; toutes les clés hors `import_*` sont supprimées. | Afficher un avertissement explicite après la réinitialisation (ce qui a été perdu), et recommander de fixer ces options dès l'étape 1. |
| G5 | **Dates ambiguës** : `format="mixed"` interprète chaque cellule séparément ; dans une même colonne, `03/04/2026` devient le 4 mars et `13/04/2026` le 13 avril. | Sonde `prepare()` avec `dayfirst=False`. | Utiliser le « Format date » du dictionnaire quand il existe ; sinon détecter une colonne au format mixte et le signaler avant tout graphique temporel. |
| G6 | **Lenteur** : seul `read_csv` est en cache. Sur le CSV réel (141 712 × 36) : `diagnose` 3,0 s, `audit` 0,7 s, `duplicated` 0,3 s, recalculés à **chaque interaction**. L'étape 6 reconstruit l'archive ZIP et le rapport JSON à chaque clic. | Mesures directes du moteur (pas encore mesurées dans l'interface). | `st.cache_data` sur diagnostic, audit, statistiques et profil, avec clé = `source_id` + dictionnaire + règles ; archive construite à la demande. À chiffrer en Mission 3. |
| G7 | Les **zéros initiaux** des identifiants sont perdus par défaut (`001` → `1` dans l'aperçu) ; l'option corrective est repliée dans la barre latérale. | Aperçu étape 1. | Conserver les options repliées, mais afficher à l'étape 1 une information lorsqu'une colonne proposée comme Identifiant a été lue comme nombre. |

#### Mineurs

| # | Problème | Correction proposée |
|---|---|---|
| M1 | Deux endroits pour les rôles : le dictionnaire (étape 2) et « Confirmer les rôles » (étape 5). Les rôles du dashboard sont déduits des données nettoyées tant que le dictionnaire n'a pas été enregistré. | Initialiser les rôles du dashboard depuis le dictionnaire. |
| M2 | Aucune mention à l'étape 5 que les données ne sont pas certifiées lorsque aucune règle n'est définie (la mention existe aux étapes 3 et 6). | Ajouter une ligne d'information au début de l'étape 5. |
| M3 | Bruit dans les tests : « missing ScriptRunContext » et `ResourceWarning` sur un dossier temporaire. Sans effet. | Aucune, ou filtrer les journaux dans les tests. |

#### Vérifiés sans problème

- `use_container_width` : **absent du code** ; `width="stretch"` est utilisé, compatible avec Streamlit 1.66. Rien à corriger.
- Noms de colonnes avec point, crochets, deux-points, espaces (`prix.ht`, `cat[1]`, `a:b`, `date de vente`) : toutes les suggestions s'affichent. Les champs Altair sont des noms internes (`Groupe`, `Valeur`, `X`, `Y`).
- Nouvel import d'un autre fichier : pas d'exception, retour à l'étape 1, l'ancienne sélection « colonnes texte » est vidée, aucun état obsolète (dictionnaire, nettoyage) conservé.
- Conversion impossible bloquée par défaut : message clair (« montant : 1 conversions impossibles… »).
- Marqueurs « ? » : restent des valeurs jusqu'au clic « Reconnaître ? comme vide ».
- Doublons stricts : signalés (1), non retirés par défaut.

### 4. Ce qui n'a pas été vérifié

- Le rendu visuel dans un navigateur (AppTest exécute le script mais n'affiche pas les graphiques Altair).
- Le parcours de l'interface avec le CSV réel (prévu en Mission 3).
- Le lancement Docker.
- L'audit détaillé des filtres, du dashboard, des règles qualité et des répétitions déjà présents.

### 5. Décision attendue

Valider la liste des corrections pour la Mission 2 (par défaut : B1, B2, G1 à G5, G7 et M1, M2 ; G6 traité en Mission 3).

---

## Mission 2 — Corrections validées : rapport

Date : 2026-10-22 · Liste appliquée : celle proposée par défaut dans la Mission 1 (B1, B2, G1 à G5, G7, M1, M2). G6 (lenteur) est reporté à la Mission 3.

### 1. Modifications

| # | Fichier | Changement | Pourquoi |
|---|---|---|---|
| B1 | `src/visualization.py` (`chart_data`) | L'index est nommé `Groupe` (et `Série`) **avant** `reset_index`, au lieu de renommer les colonnes après. | Une colonne `Valeur` entrait en collision avec la colonne de résultat. |
| B2 | `src/visualization.py` (nouvelle `parse_dates`, utilisée par `prepare`) | Une colonne numérique au rôle Date est lue comme une **année** (`%Y`). Un nombre non entier ou hors format est compté comme invalide. | Avant, 2023 devenait 1970-01-01 sans aucun signalement. |
| G5 | `src/visualization.py` (`parse_dates`) | Un **seul format par colonne** : ISO 8601 d'abord ; sinon le format est déduit de la première valeur non ISO, en tenant compte de l'option jour/mois. Les valeurs qui ne respectent pas ce format sont comptées comme invalides et affichées. | `format="mixed"` interprétait chaque cellule séparément. |
| G2 | `src/analysis.py` (`statistics(data, exclude=())`), `src/app.py` | Les colonnes déclarées **Identifiant** ou **Date** dans le dictionnaire sont exclues des statistiques, des corrélations, de l'histogramme d'exploration et des statistiques du rapport. Une légende indique les colonnes exclues et où corriger le rôle. | Des statistiques étaient calculées sur `id`. |
| G1 | `src/app.py` (étape 4) | « Cellules manquantes (marqueurs reconnus inclus) » : le brut est compté avec les mêmes marqueurs que le nettoyé. La jointure des statistiques brut / nettoyé passe en `outer`. | Le tableau affichait 1 → 3. La jointure `outer` est nécessaire depuis G2 : sinon une colonne présente seulement dans le nettoyé (convertie en Nombre) disparaissait du tableau. |
| G3 | `src/diagnostics.py`, `src/app.py`, `src/cleaning_ui.py` | Nouveau constat `numeric_hints` : colonne restée texte dont plus de la moitié des valeurs renseignées sont des nombres. On affiche le nombre de valeurs non numériques et jusqu'à 5 exemples, aux étapes 2 et 3. **Ni le type ni le rôle ne sont modifiés.** | Le cas `montant = abc` passait inaperçu. |
| G4 | `src/app.py` | Avertissement après réinitialisation lorsque le **même fichier** est relu avec d'autres options **et** qu'un travail existait (dictionnaire modifié, règles, prévisualisation, versions, graphiques, répétitions). Légendes ajoutées sous les options de lecture. | La session était effacée sans prévenir. |
| G7 | `src/app.py` (étape 1) | Information lorsqu'une colonne proposée comme Identifiant a été lue comme nombre. | Les zéros initiaux disparaissaient sans signalement. |
| M1 | `src/dashboard.py` | Les rôles du dashboard sont initialisés depuis le dictionnaire (ils restent modifiables à l'étape 5). | Les rôles étaient définis à deux endroits. |
| M2 | `src/app.py` (étape 5) | Bandeau « Évaluation des règles : … Les graphiques ne certifient pas l'exactitude métier des données. » | La mention manquait à l'étape 5. |

Autres changements :
- Le constat G3 convertit seulement les **valeurs distinctes**. Une première version faisait passer `diagnose` de 3,0 s à 9,0 s sur le CSV réel ; la version actuelle prend 3,9 s.
- L'avertissement pandas « Parsing dates in %d/%m/%Y… » est neutralisé dans `parse_dates`, car les conversions impossibles sont déjà signalées à l'utilisateur.
- Nouvelles clés de session : `dictionary_initial` (comparaison pour G4) et `import_payload_sha` (préservée lors d'une réinitialisation, comme les autres clés `import_*`).

### 2. Tests

`python -m unittest discover -s src/tests` → **45 tests, OK** (38 existants + 7 nouveaux).

| Nouveau test | Couvre |
|---|---|
| `test_visualization.test_group_column_names_do_not_collide_with_result_columns` | B1 : colonnes `Valeur`, `Groupe`, `Série` en Barres, Tableau croisé, Courbe |
| `test_visualization.test_numeric_dates_are_years_never_nanoseconds` | B2 |
| `test_visualization.test_ambiguous_dates_use_one_format_per_column` | G5 : `03/04` / `13/04`, avec et sans l'option jour/mois |
| `test_analysis.test_statistics_exclude_declared_identifiers` | G2 (moteur) |
| `test_diagnostics.test_mostly_numeric_text_is_reported_without_changing_type` | G3 : constat seulement ; pas de constat pour un identifiant, un texte ou un type Nombre déclaré |
| `test_app.test_sample_csv_through_all_steps` | 6 étapes sur `exemple.csv` : G7, G3, G2, G1, M2, M1 |
| `test_app.test_changing_read_options_after_work_is_announced` | G4 : pas d'avertissement sans travail ; avertissement affiché une seule fois après perte de travail |

### 3. Lancement et essais

- `python -m streamlit run src/app.py` : le serveur démarre et le contrôle de santé répond `ok`.
- **CSV d'exemple** : 6 étapes, aucune exception. Les sondes de la Mission 1 ont été rejouées : les 18 suggestions s'affichent, y compris pour `Valeur`.
- **CSV réel** (`data/raw/incident_event_log.csv`, 141 712 × 36) : 6 étapes, aucune exception ni erreur. Temps par étape mesurés avec AppTest (pas dans un navigateur) : 1 : 6,4 s · 2 : 5,6 s · 3 : 5,1 s · prévisualisation : 6,6 s · 4 : 11,7 s · 5 : 7,3 s · 6 : 9,9 s.
- **G5 confirmé sur le CSV réel** : `closed_at = "5/3/2016 12:00"` était lu comme le 3 mai, alors que les valeurs non ambiguës de la même colonne étaient lues jour-mois. Désormais : 85 396 valeurs signalées comme invalides sans l'option jour/mois ; avec l'option, 0 invalide et la date lue est le 5 mars.

### 4. Non vérifié / limites restantes

- Rendu visuel dans un navigateur (AppTest seulement).
- Lenteur (G6) : inchangée, voire légèrement accrue par G3 (+0,9 s sur `diagnose`). À traiter en Mission 3.
- **Nouveau constat, non corrigé** : la colonne réelle `sys_updated_by` est proposée comme **Date**, car `infer_roles` cherche « date » dans le nom et le trouve dans « up**date**d ». Le rôle reste corrigeable. Proposition : n'utiliser que des mots entiers (`date`, suffixe `_at`).
- G3 repose sur un seuil d'observation (plus de la moitié des valeurs sont des nombres). Ce n'est pas une règle métier : rien n'est modifié automatiquement.
- G5 : si la première valeur non ISO suit un format différent du reste de la colonne, beaucoup de valeurs seront signalées comme invalides. C'est visible, mais il faudra alors renseigner le « Format date » du dictionnaire ou choisir le type Date.

---

## Mission 3 — Test de charge : rapport

Date : 2026-10-22 · Fichier : `data/raw/incident_event_log.csv` (46 Mo, 141 712 lignes × 36 colonnes, « ? » fréquent).

### 1. Méthode

- Parcours des 6 étapes avec `streamlit.testing.v1.AppTest`, en chronométrant les fonctions du moteur.
- Deux mesures par étape : l'arrivée sur l'étape, puis une **interaction** (un rerun, comme un clic sur n'importe quel widget).
- Temps côté serveur seulement : le rendu dans le navigateur n'est pas mesuré.

### 2. Résultats avant / après

| Étape | Avant | Après |
|---|---|---|
| 1 Découverte (import) | 3,1 s | 2,9 s |
| 1 Découverte (interaction) | 0,5 s | 0,2 s |
| 2 Exploration | 5,6 s | 2,0 s |
| 2 Exploration (interaction) | 5,6 s | **0,3 s** |
| 3 Nettoyage | 5,0 s | 0,3 s |
| 3 Nettoyage (interaction) | 5,0 s | **0,3 s** |
| 3 Prévisualisation | 6,5 s | 0,9 s |
| 3 → 4 Validation + Comparaison | 11,9 s | 3,4 s |
| 4 Comparaison (interaction) | 3,3 s | **0,2 s** |
| 5 Visualisation | 7,3 s | 2,3 s |
| 5 Visualisation (interaction) | 7,8 s | **0,3 s** |
| 6 Synthèse / export | 9,9 s | 0,3 s |
| 6 Synthèse / export (interaction) | 9,7 s | **0,3 s** |

Mémoire du processus : 429 Mo après l'import, 532 Mo en fin de parcours.

### 3. Causes trouvées

1. **Tout était recalculé à chaque interaction.** Seule la lecture du CSV était en cache. Le diagnostic (3,5 s), l'audit (0,7 s), la normalisation des vides (0,7 s, jusqu'à 6 fois par rerun), les doublons et la préparation des graphiques (1,5 s) étaient refaits à chaque clic.
2. **L'archive ZIP (5,2 s) et les CSV de téléchargement** étaient construits à chaque affichage de l'étape 6, même sans clic.
3. **Traitement cellule par cellule** alors que le fichier contient peu de valeurs distinctes : repérage des marqueurs (1,7 s), normalisation des vides, lecture des dates (1,2 s).

### 4. Modifications

| Fichier | Changement |
|---|---|
| `src/session_cache.py` (nouveau) | `cached(fn, data, *params)` : mémorisation propre à la session. La clé combine la fonction, l'objet de données et le contenu JSON des paramètres (dictionnaire, règles, rôles…). Au plus 12 entrées, la plus ancienne est retirée en premier. Le cache est effacé avec la session lors d'un nouvel import. |
| `src/app.py` | Le brut reste le **même objet en session** : il n'est plus relu ni copié à chaque rerun. Diagnostic, audit, statistiques, profil, doublons, normalisation et répétitions passent par `cached`. Les fichiers à télécharger (données nettoyées, rejets, archive ZIP) sont **générés au clic** : `st.download_button` reçoit une fonction. |
| `src/cleaning_ui.py`, `src/quality_ui.py`, `src/dashboard.py`, `src/repetitions_ui.py` | Diagnostic, audit, doublons, préparation des graphiques et normalisation passent par `cached`. |
| `src/analysis.py` | Nouvelle fonction `duplicate_rows(data)`. |
| `src/quality.py` (`normalize_missing`) | Le test des vides et marqueurs porte sur les **valeurs distinctes**. Normalisation : 0,75 s → 0,25 s. |
| `src/diagnostics.py` (`diagnose`) | Marqueurs suspects et constat « colonne surtout numérique » calculés sur les valeurs distinctes et leurs effectifs. Diagnostic : 3,5 s → 0,9 s. |
| `src/visualization.py` (`parse_dates`) | Dates converties une fois par valeur distincte, puis reportées sur chaque ligne. Préparation des graphiques : 1,45 s → 0,8 s. |
| `src/visualization.py` (`infer_roles`) | Correction annoncée en Mission 2 : « update » ne fait plus proposer le rôle Date (`sys_updated_by` devient Catégorie ; `sys_updated_at` reste Date). |

**Équivalence vérifiée sur le CSV réel** (comparaison avec l'ancien code) : vides normalisés identiques (avec et sans marqueur « ? », y compris une cellule d'espaces), 18 marqueurs suspects identiques, dates identiques avec et sans l'option jour/mois.

### 5. Tests et lancement

- `python -m unittest discover -s src/tests` → **46 tests, OK** (1 nouveau : `test_updated_by_is_not_proposed_as_date`). Les tests d'interface existants qui modifient les marqueurs, le dictionnaire ou les règles passent : le cache est bien recalculé quand ces entrées changent.
- Serveur `streamlit run src/app.py` démarré, contrôle de santé `ok`.
- CSV d'exemple et CSV réel : 6 étapes, aucune exception.

### 6. Non vérifié / limites

- **Le clic sur les boutons de téléchargement n'a pas été testé dans un navigateur.** La génération au clic est documentée par la version installée (Streamlit 1.66), mais AppTest ne déclenche pas le téléchargement.
- Le rendu navigateur des grands tableaux n'est pas mesuré.
- Le premier passage sur l'étape 2 ou 5 coûte encore environ 2 s. La validation d'un nettoyage coûte 3,4 s : écriture des CSV de la version dans l'historique de l'archive.
- Au-delà de 12 calculs mémorisés, le plus ancien est recalculé au besoin (environ 1 s).

### 7. Optimisations proposées, non appliquées

| Proposition | Effet attendu |
|---|---|
| Limiter l'affichage des grands tableaux (rejets, enregistrements à investiguer, groupes de répétitions) à 1 000 lignes, avec mention et export complet. | Évite d'envoyer des dizaines de milliers de lignes au navigateur. |
| Filtres sur les identifiants à forte cardinalité (ex. `number`, environ 24 000 valeurs) : recherche ou saisie au lieu d'une liste de toutes les valeurs. | Liste déroulante utilisable ; c'est un sujet de la Mission 4. |
| Conserver les versions validées en tableaux et ne les écrire en CSV qu'au moment de l'archive. | Validation environ 2,5 s plus rapide ; mémoire équivalente. |

---

## Mission 4 — Filtres, caractère générique et nettoyage du code : rapport

Date : 2026-10-22 · Périmètre : `src/` uniquement (notebooks, Power BI, Docker et `requirements.txt` racine non modifiés).

### 1. Vérification du caractère générique

**Code :** aucune colonne, valeur ou règle propre au jeu « incidents » n'est codée en dur dans `src/` (recherche de `incident`, `sla`, `caller`, `priority`, `number`…). Seul biais trouvé : l'heuristique des rôles ne connaissait que des mots anglais.

**Essais sur des CSV d'autres domaines**, générés pour l'occasion (non versionnés) :

| CSV | Particularités | Avant correction | Après |
|---|---|---|---|
| Ventes FR | `;`, décimale `,`, cp1252, accents, `N° commande` à zéros, dates jj/mm, colonne vide | `N° commande` → **Mesure** (somme des numéros proposée) | Identifiant + info « zéros initiaux » |
| RH | `matricule` à zéros, `NA`, booléens, texte avec virgules | `matricule` → **Mesure** | Identifiant + info |
| Ferroviaire | retards négatifs, `horodatage` ISO avec fuseau | `horodatage` → **Catégorie** | Date |
| Une ligne, en-têtes en double, une seule colonne | cas limites | OK | OK |

Pour chacun : 6 étapes, filtres globaux sur toutes les colonnes, toutes les suggestions de graphiques affichées, ajout d'un graphique → **aucune exception**.

### 2. Filtres (globaux + par graphique, intersection, effectifs)

Déjà présents et conformes : filtres globaux appliqués à tous les graphiques, filtres locaux par graphique, combinaison par intersection, choix d'inclure ou non les valeurs manquantes, nombre de lignes retenues affiché.

Problème bloquant trouvé sur le CSV réel : pour un identifiant comme `number` (24 918 valeurs), **toutes les valeurs étaient présélectionnées**. Il fallait 15,7 s pour afficher le filtre et 21,7 s pour l'appliquer, et la configuration JSON aurait enregistré les 24 918 valeurs.

### 3. Modifications

| Fichier | Changement | Pourquoi |
|---|---|---|
| `src/visualization.py` (`apply_filters`, `validate_configuration`) | Filtre de catégorie avec un champ `exclude` facultatif (défaut `False`, donc les anciennes configurations restent valides). | Exclure quelques valeurs sans en sélectionner des milliers. |
| `src/dashboard.py` (`filter_editor`) | Mode « Retenir / Exclure ». Jusqu'à 50 valeurs : toutes retenues par défaut (comme avant). Au-delà : exclusion avec une sélection vide, donc toutes les lignes gardées. Au-delà de 1 000 valeurs : saisie libre, une valeur par ligne, avec le nombre de valeurs saisies absentes des données. | Filtre `number` : 16 s + 22 s → 0,5 s + 0,5 s. |
| `src/dashboard.py` (`render_chart`) | « N / M lignes retenues par les filtres du graphique (base : lignes après filtres globaux) ». | L'effet des filtres locaux est explicite. |
| `src/visualization.py` (`infer_roles`) | Mots du nom en français et en anglais (`n°`, `num`, `no`, `numéro`, `matricule`, `identifiant`, `réf`, `référence`, `clé`, `horodatage`, `timestamp`…) et reconnaissance des valeurs au format ISO `AAAA-MM-JJ[ hh:mm[:ss]][fuseau]`. | Rôles proposés justes hors anglais. Ce ne sont que des propositions, corrigeables. |
| `src/README.md` | Retrait des mentions « incidents » et « SLA » ; documentation des rôles, des filtres et du cache. | Documentation générique. |

### 4. Code mort et doublons supprimés

| Élément | Constat | Action |
|---|---|---|
| `clean()` (`src/analysis.py`) : normalisation des espaces, suppression des doublons, suppression de lignes, `preserve_index` | Jamais atteints par l'application : `pipeline()` les réalise déjà (mises en rejet). Logique en double, utilisée seulement par des tests. | `clean(data, rules)` ne fait plus que les remplacements. Tests réécrits ; ces comportements restent testés au niveau de `pipeline` (`test_quality`). |
| Réinitialisation du dashboard | Écrite deux fois (`dashboard.py`, `quality_ui.py`). | Fonction unique `reset_dashboard()`. |
| `pipeline` importé dans `app.py` | Non utilisé. | Import retiré. |
| Imports inutilisés dans `test_app.py` | Non utilisés. | Retirés. |

Vérification : `pyflakes src` → aucun signalement. Toutes les fonctions restantes sont appelées par l'application.

### 5. Tests et lancement

`python -m unittest discover -s src/tests` → **49 tests, OK**. Nouveaux tests :
- `test_roles_from_french_names_and_iso_content`
- `test_exclusion_filter_and_missing_values`
- `test_high_cardinality_filters_keep_all_rows_by_default`
- `test_unknown_category_and_row_removal_left_to_pipeline`

`test_preserves_source_and_index` remplace l'ancien test de `clean()`. Les clés de widgets ont été mises à jour dans `test_dashboard` (mode ajouté à la clé).

Essais : CSV d'exemple, 6 CSV génériques, CSV réel → aucune exception.

### 6. Non vérifié / limites

- Rendu navigateur des filtres (radio et zone de saisie).
- Les en-têtes en double sont renommés par pandas (`x` → `x.1`) sans message.
- Les dates jj/mm restent reconnues par le nom de la colonne, pas par leur contenu (seul l'ISO est reconnu par le contenu, car il n'est pas ambigu).
- `src/README.md` cite encore le service Docker `itservice` : ce nom vient de `compose.yaml`, hors du périmètre `src/`.
- `pyflakes` a été installé dans le `.venv` pour l'analyse : il sera désinstallé à la fin.

---

## Mission 5 — Dashboard : ordre, largeur, modification : rapport

Date : 2026-10-22 · Périmètre : `src/`.

### 1. Constat

Déjà présents : ajout depuis une suggestion ou l'éditeur, modification d'un graphique (« Point de départ → Modifier »), largeur demi ou pleine, retrait, export et import JSON, 30 graphiques au maximum.

Problème : deux réglages concurrents pour l'ordre.
- Un numéro de **« Ligne »** (1 à 30), présent à la fois dans l'éditeur et dans la disposition.
- Une **« Position dans l'ordre »**.

L'affichage triait d'abord par ligne, puis par position. Démonstration : avec 3 graphiques, passer le n° 1 en ligne 2 l'affiche **en dernier**, alors qu'il reste « 1 · » dans la liste. Le titre et la largeur se modifiaient aussi à deux endroits (éditeur et disposition).

### 2. Modifications

| Fichier | Changement | Pourquoi |
|---|---|---|
| `src/dashboard.py` | **Ordre unique** : affichage dans l'ordre de la liste ; deux demi-largeurs consécutives partagent une rangée ; une pleine largeur occupe sa rangée. Champ « Ligne » retiré de l'éditeur et de la disposition. | La numérotation de la liste correspond à ce qui est affiché. |
| `src/dashboard.py` | La disposition ne règle plus que **la largeur et la position** (« 1 = en haut »). Le titre, le calcul et les filtres se modifient dans l'éditeur. | Chaque réglage n'a plus qu'un seul endroit. |
| `src/dashboard.py` | Bouton **« Modifier ce graphique »** dans la disposition : il ouvre l'éditeur sur ce graphique. La sélection de l'éditeur a une clé, nettoyée si le graphique est retiré. | Modification directe d'un graphique existant. |
| `src/dashboard.py` (restauration) | Ancienne configuration contenant `row` : graphiques triés par ligne (tri stable), puis `row` retiré. | Les dashboards JSON déjà exportés restent utilisables avec la même disposition. |
| `src/visualization.py` | `row` facultatif dans `validate_configuration` (validé s'il est présent) ; retiré des suggestions. | Compatibilité. |
| `src/README.md` | Section de disposition réécrite. | — |

Une modification d'un graphique garde sa position et sa largeur.

### 3. Tests

- `test_build_edit_filter_and_remove` adapté : largeur et position au lieu de « Nouvelle ligne ».
- `test_display_follows_list_order_and_edit_shortcut` : l'ordre affiché suit la liste après déplacement ; « Modifier ce graphique » ouvre l'éditeur (« Mettre à jour le graphique ») ; retrait sans exception.
- `test_legacy_rows_are_converted_to_order` : import d'un JSON avec `row` → ordre par ligne, champ retiré.

### 4. Non vérifié / limites

- Rendu visuel des rangées dans un navigateur.
- Pas de glisser-déposer : on déplace un graphique en saisissant sa position.
- Les fichiers JSON exportés ne contiennent plus `row`. Une ancienne version de l'application ne pourrait pas les relire (son validateur exigeait `row`).

---

## Mission 6 — Règles de qualité : rapport

Date : 2026-10-22 · Périmètre : `src/`.

### 1. Constat

Déjà présents et vérifiés :
- **Complétude** (« Obligatoire ») et **unicité** (« Unique »), plus intervalle, catégories autorisées, format, ordre de dates et clé composée.
- Seuil d'anomalies toléré (%) et priorité P1 / P2 / P3 dans le formulaire de règle.
- Règles **rejouées** sur le brut (étape 2), sur la prévisualisation (étape 3) et avant / après (étape 4).
- « Conforme » = taux ≤ seuil. Sans aucune règle : « À évaluer ». Un échec P1 suggère NO-GO ; la décision reste à l'utilisateur.

Écart avec le cahier : « une baisse d'anomalies due à des exclusions n'est pas une correction : l'interface le dit ». L'étape 4 n'avait qu'une phrase générale dans un volet replié : impossible de savoir combien d'anomalies avaient disparu par exclusion plutôt que par correction.

### 2. Modifications

| Fichier | Changement |
|---|---|
| `src/quality.py` | Nouvelle fonction `compare_audits(before, before_details, after, after_details, kept_index)`. Pour chaque règle, elle ajoute à la comparaison : **écartées par exclusion de lignes** (enregistrements en anomalie avant, absents du nettoyé), **résolues sur lignes conservées** (en anomalie avant, conservés, plus en anomalie après), **nouvelles anomalies** (apparues après nettoyage). |
| `src/app.py` (étape 4) | Tableau des règles avant / après **visible** (plus replié). Avertissement chiffré quand des anomalies ont disparu par exclusion : « N anomalies ont disparu parce que leurs lignes ont été écartées (rejets) : ce n'est pas une correction des données ». Sans règle : message explicite (rien ne certifie les données). Légende : « Conforme » ne certifie pas l'exactitude métier. |
| `src/app.py` (étape 6) | `comparaison_controles` ajouté au rapport JSON (donc à l'archive). |
| `src/README.md` | Étape « Comparaison » documentée. |

**Essai sur le CSV réel** : règles « `caller_id` obligatoire » (« ? » reconnu comme vide) et « `number` unique », nettoyage « supprimer les lignes » sur `caller_id`.
- `caller_id` : 29 → 0 anomalies, dont **29 écartées par exclusion** et 0 résolue.
- `number` : 141 712 → 141 683, **non conforme**. Le fichier est un journal d'événements : un même numéro revient plusieurs fois. L'outil le montre sans conclure que c'est une erreur ; la règle était un choix de l'utilisateur.
- Avertissement affiché : 58 anomalies disparues par exclusion.

### 3. Tests

- `test_quality.ComparisonTests.test_exclusions_are_not_counted_as_corrections` : unicité, complétude et seuil (P3 à 25 % conforme), exclusions comptées comme telles.
- `test_quality.ComparisonTests.test_imputation_is_a_resolution_on_kept_rows` : un remplacement par la médiane compte comme résolution, pas comme exclusion.
- `test_app.test_comparison_separates_exclusions_from_corrections` : message « aucune règle » ; puis unicité de `id` et suppression des doublons sur l'exemple → 2 avant, 0 après, 1 écartée, 1 résolue, avertissement affiché.

`python -m unittest discover -s src/tests` → **54 tests, OK**.

### 4. Non modifié — proposition

Complétude et unicité peuvent se déclarer de deux façons :
- par les cases du **dictionnaire** : seuil fixe de 0 %, priorité P1 si « Critique », sinon P2 ;
- par le **formulaire de règle** : seuil libre et P1 / P2 / P3.

Je ne l'ai pas supprimé, car c'est une fonctionnalité utilisée, mais une même règle peut ainsi apparaître deux fois. Proposition : garder les cases du dictionnaire comme raccourci, et signaler à l'ajout une règle déjà déclarée pour la même colonne.

### 5. Non vérifié / limites

- Rendu navigateur de l'étape 4.
- Pour l'unicité, écarter une occurrence « résout » aussi l'autre : c'est indiqué dans la légende.

---

## Mission de nettoyage — Étapes 0 et 1 : état de départ et audit (lecture seule)

Date : 2026-10-22 · Branche créée : `nettoyage` (depuis `powerbi-updates`) · Aucun fichier du dépôt modifié.

### Étape 0 — État de départ

**Git n'est pas propre.** Fichiers jamais commités : tout `src/`, `docs/MISSIONS_MVP.md`, `docs/RAPPORT_MISSIONS.md`, `Dockerfile`, `compose.yaml`, `.dockerignore`. `git mv` ne marche que sur des fichiers suivis : un commit de départ est nécessaire avant de restructurer.

| Mesure | Résultat |
|---|---|
| Tests | **54 tests OK en 24,1 s** (`python -m unittest discover -s src/tests`) |
| Application | serveur démarré, `/_stcore/health` = ok ; 6 étapes sans exception sur `exemple.csv` (AppTest) |
| Référence de comportement | scénario fixe sur `exemple.csv` et sur le CSV réel. **Exécuté deux fois : contenus identiques** (horodatages UTC et uuid neutralisés). |

Contenu de la référence (dossier `scratchpad/reference_etape0/`, hors dépôt) :

| | exemple.csv | CSV réel |
|---|---|---|
| Scénario | `id` unique, « ? » reconnu, `categorie` → Inconnu, `montant` → supprimer les lignes, doublons supprimés, 1 graphique, filtre global « Exclure » | `caller_id` obligatoire + « ? », `number` unique, `caller_id` → supprimer les lignes, doublons supprimés, 1 graphique, filtre « Exclure » |
| Brut → nettoyé | 7×4 → 5×4 | 141 712×36 → 141 683×36 |
| Rejets | 2 (doublon strict, valeur manquante `montant`) | 29 (valeur manquante `caller_id`) |
| Comparaison | `id` unique : 2 → 0, 1 écartée, 1 résolue | `number` : 141 712 → 141 683 (29 écartées) ; `caller_id` : 29 → 0 (29 écartées) |
| Téléchargements hachés | 7 : données nettoyées, rejets (×2), rapport JSON, contrôles, configuration du dashboard, archive ZIP (10 fichiers hachés un par un) | idem |

Performances (CSV réel, interaction = un rerun) : 0,3 à 0,6 s. **Régression trouvée**, voir a7.

### Étape 1 — Audit

Outils : `ruff` et `vulture`, installés dans un dossier temporaire (pas dans le `.venv`), puis vérification manuelle de chaque résultat.

#### a) Code mort

| # | Où | Constat | Vérification |
|---|---|---|---|
| a1 | — | `ruff` (F) : **aucun import ni variable inutilisé** dans l'application. | — |
| a2 | `app.py:31,160,161,172,260`, `cleaning_ui.py:109`, `quality_ui.py:57` | `vulture` signale 7 « attributs inutilisés » : `workflow_step`, `reset_notice`, `import_payload_sha`, `conclusions`, `pending_step`, `sensitive`. | **Faux positifs** : clés de session relues par leur nom (`state.get("conclusions")`, `pop("pending_step")`, widget `key="workflow_step"`…). À garder. |
| a3 | `quality_ui.py:48` `context(stage="summary")` | Paramètre `stage` : un seul appel, toujours `"summary"` (`app.py:259`). La branche `if stage == "summary"` est toujours vraie. | Mort. Supprimer le paramètre ; comportement identique. |
| a4 | `quality_ui.py:70` | `state.setdefault("dictionary", records(initial_dictionary(raw)))` : `app.py:165` garantit déjà la clé. | Mort, et **coûteux** (a7). |
| a5 | `app.py:273` `"objectif": st.session_state.get("objective", "")` | La clé `objective` n'est **jamais écrite** : le champ exporté est toujours vide (rapport JSON et ligne « Objectif : » de `summary.md`). | Mort, mais le retirer **change les exports**. Je propose de le garder (décision D2). |
| a6 | `visualization.py:21,27` | `ISO_DATE` est compilé mais seul `.pattern` sert. | Mineur : garder une chaîne. |
| a7 | `app.py:164`, `quality_ui.py:70` | `setdefault(clé, calcul)` **évalue le calcul à chaque rerun** : `initial_dictionary` (inférence des rôles) tourne 1 à 2 fois par interaction (0,1 à 0,3 s sur le CSV réel). | **Régression de performance introduite en Mission 4** : interactions 0,3 à 0,6 s au lieu de 0,2 à 0,3 s. Correction : ne calculer que si la clé manque. |
| a8 | `dashboard.py:166` repli `infer_roles(data)` | Jamais atteint depuis l'application (le dictionnaire couvre toujours les colonnes). Atteint quand `dashboard()` est appelé seul (tests). | À garder. |

#### b) Code dupliqué

| # | Où | Doublon | Proposition |
|---|---|---|---|
| b1 | `quality_ui.py:95-112` et `repetitions_ui.py:60-68` | Création d'une règle de qualité à deux endroits : identifiants `Q-…` / `K-…`, priorité P1/P2/P3 redéfinie, ajout et invalidation. `validate_rule` n'est appelé que dans le premier. | Une fonction moteur `new_rule(...)` + `add_rule()` côté interface. |
| b2 | `quality.py:53`, `quality_ui.py:95`, `repetitions_ui.py:60` | Liste `P1/P2/P3` ×3. | Constante `PRIORITIES`. |
| b3 | `dashboard.py:224,258`, `visualization.py:231,234` | Largeurs `Demi/Pleine` et options de tri, chacune en double. | Constantes `WIDTHS`, `SORTS`. |
| b4 | `app.py:111` et `dashboard.py:99` | Bornes de Tukey (1,5 × IQR) calculées deux fois, dans l'interface. | Fonction moteur `tukey_bounds(values)`. |
| b5 | `cleaning_ui.py:104-105` et `quality_ui.py:15` | Liste des clés à effacer (`decision`, `decision_reason`) en double. | Réutiliser une fonction unique. |
| b6 | `cleaning_ui.py:66` et `quality_ui.py:116` | Libellé « ID · colonne · règle » d'une règle construit deux fois. | Fonction `rule_label()`. |
| b7 | `app.py:164-165` et `quality_ui.py:70` | Initialisation du dictionnaire (a4). | Un seul endroit. |
| b8 | Rôles : `dictionary[*]["Rôle"]` (étape 2) et `viz_roles` (étape 5) | Deux sources de vérité pour les rôles, voulues en M1 (le dashboard part du dictionnaire puis peut diverger). | Pas un doublon de code. À garder ; à documenter. |
| b9 | `app.py:229` et `app.py:298` | Deux boutons « rejets » (étapes 4 et 6) pour le même fichier. | Choix d'ergonomie. À garder. |

**Valeurs « magiques »** (à regrouper dans un fichier de configuration unique) :

| Valeur | Endroits |
|---|---|
| 5 000 points / lignes tracées | `dashboard.py:115,116,135` |
| 1 000 valeurs hors moustaches | `dashboard.py:107,108` |
| 1 000 / 50 valeurs distinctes (filtres) | `dashboard.py:17,19` |
| 30 graphiques | `dashboard.py:240,241`, `visualization.py:187,188,234` |
| 100 groupes | `dashboard.py:226`, `visualization.py:236` |
| 200 caractères | `dashboard.py:222`, `visualization.py:236`, `quality.py:63-64` |
| 2 Mo (configuration JSON) | `dashboard.py:290` |
| 20 lignes d'aperçu / groupes | `app.py` (`head(20)` ×3), `visualization.py` (limite par défaut) |
| 30 / 20 classes d'histogramme | `dashboard.py:91`, `app.py` |
| 12 entrées de cache | `session_cache.py` |

#### c) Fichiers trop longs, ou qui mélangent calcul et affichage

| Fichier | Lignes | Constat |
|---|---|---|
| `app.py` | 304 | 186 lignes de script hors fonctions. Contient les **6 étapes à la fois** (navigation, étapes 1, 4, 5, 6) et du **calcul** : construction du rapport JSON (`app.py:270-300`, environ 30 lignes), tableau avant/après, histogramme et bornes IQR (`explore`, 51 lignes). |
| `dashboard.py` | 302 | `dashboard()` fait **160 lignes** (complexité 28) : rôles, filtres globaux, éditeur, aperçu, disposition, rendu en grille, sauvegarde JSON. `render_chart` : 63 lignes. |
| `cleaning_ui.py` | 113 | `cleaning_screen()` fait **100 lignes** (complexité 15) : diagnostic, formulaire, prévisualisation, validation. |
| `quality.py` | 234 | Moteur pur (correct). `audit` (57 lignes, chaîne de `if` par type de contrôle) et `pipeline` (62 lignes, **10 paramètres**). |
| `visualization.py` | 239 | Moteur pur. `validate_configuration` : 59 lignes, complexité 26. |
| `repetitions.py` / `repetitions_ui.py` | 66 / 70 | `inspect_repetitions` : 55 lignes ; `repetition_editor` : 58 lignes. |
| `session_cache.py` | 23 | Importe Streamlit, mais c'est de la logique commune (à placer dans `core/`). |

Séparation actuelle : moteur sans Streamlit = `analysis`, `quality`, `diagnostics`, `visualization`, `repetitions`, `reporting` ; interface = `app`, `cleaning_ui`, `quality_ui`, `repetitions_ui`, `dashboard`. Le rangement suit le type de code, pas l'étape du parcours.

#### d) Noms propres à l'IT

| Où | Constat | Proposition |
|---|---|---|
| Code de l'application | **Aucun** (recherche : incident, sla, caller, assignment, ticket, priority…). « Priorité » et P1/P2/P3 sont des notions génériques de qualité. | — |
| `compose.yaml:1,4,7` | Projet `itservice-analytics`, service `itservice`, variable `ITSERVICE_PORT`. | Renommer en `analyse-csv` / `ANALYSE_PORT` (le cahier autorise Docker si les chemins changent). Décision D3. |
| `src/README.md:26,33` | Commandes `logs itservice`, `ITSERVICE_PORT`. | Suivre D3. |
| Tests : `test_app.py:168,189` (`incidents.csv`), `test_dashboard.py:14,50` et `test_visualization.py:14-37` (`opened_at`) | Noms de jeux de test à saveur IT. | Renommer en noms neutres (`donnees.csv`, `date_ouverture`) ; comportement testé identique. |

#### e) Tests (54) : ce qu'ils protègent

N = nécessaire · R = redondant · O = obsolète · F = fragile (dépend d'un détail d'implémentation). Un test peut être N et F : il faut alors le rendre plus robuste, pas le supprimer.

**test_app.py (9, interface via AppTest)**

| Test | Protège | Classe |
|---|---|---|
| `test_missing_counts_are_visible_before_targeted_choices` | Diagnostic chiffré avant les choix ; choix seulement pour les colonnes concernées ; remplacement ; journal automatique | N, F (`app.radio[0]`, `app.dataframe[0]`) |
| `test_sample_csv_through_all_steps` | 6 étapes sur l'exemple ; info zéros initiaux ; constat numérique ; identifiants exclus ; avant/après ; « non certifié » ; rôles issus du dictionnaire | N, F (index) |
| `test_comparison_separates_exclusions_from_corrections` | Distinction exclusion / correction ; message sans règle | N |
| `test_changing_read_options_after_work_is_announced` | Avertissement avant effacement | N |
| `test_special_markers_require_explicit_choice` | Les marqueurs restent des valeurs tant qu'ils ne sont pas déclarés | N, F (`dataframe[0]`) |
| `test_discovery_precedes_optional_business_notes` | Aucune saisie obligatoire avant de voir le fichier | N ; **la ligne 128 (« Noter ce que ») est O** : ce texte n'existe plus nulle part, l'assertion est toujours vraie |
| `test_repetition_analysis_does_not_change_cleaned_data` | Les répétitions ne modifient ni les données ni le nettoyage ; règle composée explicite ; nouvel import réinitialise | N |
| `test_guided_workflow` | Remplacement par la moyenne + parcours des étapes 3 à 5 | **R** : le remplacement via l'interface est couvert par `test_missing_counts…`, le parcours complet par `test_sample_csv…`. Et **F** : `app.button[0]`. |
| `test_quality_workflow_and_protected_identifiers` | Zéros initiaux ; conversion mise en rejet ; versions conservées après modification du dictionnaire | N |

**test_dashboard.py (7, interface du dashboard)**

| Test | Protège | Classe |
|---|---|---|
| `test_build_edit_filter_and_remove` | Filtre global appliqué ; largeur et position ; retrait | N (en partie couvert par `test_display…`, mais c'est le seul qui teste l'application d'un filtre global via l'interface) ; F (clé de widget) |
| `test_all_suggested_chart_types_render` | Les 6 types de graphique s'affichent | N |
| `test_restore_and_edit_local_filters` | Filtre local + export / réimport JSON | N, F (clé de widget) |
| `test_display_follows_list_order_and_edit_shortcut` | Ordre affiché = ordre de la liste ; « Modifier » ; retrait | N |
| `test_legacy_rows_are_converted_to_order` | Compatibilité des anciens JSON | N |
| `test_high_cardinality_filters_keep_all_rows_by_default` | Mode Retenir / Exclure ; saisie libre ; effectifs | N, F (clés de widget) |
| `test_large_histogram_and_box_use_all_values` | Pas d'échantillonnage des histogrammes et boîtes au-delà de 5 000 valeurs | N, F (« aucun avertissement du tout ») |

**test_visualization.py (12, moteur)** : tous N.
- `roles_conversion_and_source_preservation`, `roles_from_french_names_and_iso_content`, `updated_by_is_not_proposed_as_date` : rôles. Les deux derniers pourraient être fusionnés, mais ils ne sont pas redondants.
- `intersection_and_missing_filters`, `exclusion_filter_and_missing_values`, `end_date_includes_entire_day` : filtres.
- `aggregation_sort_and_excluded_rows`, `empty_month_is_not_zero_sum` (absence ≠ zéro), `group_column_names_do_not_collide…` : agrégations.
- `numeric_dates_are_years…`, `ambiguous_dates_use_one_format…` : dates.
- `round_trip_and_reject_invalid_configuration` : configuration JSON.

**test_quality.py (9, moteur)** : tous N.
- `audit_explains_violations…` : brut intact, références sources.
- `invalid_conversion_blocks_by_default` : conversions bloquées.
- `conversion_rejects_and_imputation_are_traceable` : rejets tracés, journal.
- `rejected_values_do_not_influence_mean`.
- `duplicate_and_missing_rejections_account_for_all_rows`.
- `recommendation_depends_on_defined_controls` : P1 → NO-GO, sans règle → « À évaluer ».
- `date_format_and_trim…`.
- `ComparisonTests` ×2 : exclusion / correction.

**test_analysis.py (6, moteur)** : tous N.
- `preserves_source_and_index`, `imputation_is_independent_of_rule_order`, `all_missing_rejects_imputation`, `unknown_category_and_row_removal_left_to_pipeline` : contrat de `clean()`.
- `descriptive_statistics`, `statistics_exclude_declared_identifiers` : statistiques.

**test_diagnostics.py (3)**, **test_repetitions.py (7)**, **test_reporting.py (1)** : tous N.
- Diagnostics : vides et marqueurs séparés ; conversions distinguées ; constat numérique sans changement de type.
- Répétitions : caractère générique (rail / RH) ; clés incomplètes ; aucune modification des données ; règle composée explicite.
- Rapport : archive ZIP avec le brut inchangé.

**Bilan des tests :**
- 1 redondant (`test_guided_workflow`) et 1 assertion obsolète (ligne 128).
- Les autres sont nécessaires. Aucun test ne vise une fonction disparue.
- **Fragilité principale** : navigation par `app.radio[0]`. Elle casse dès qu'un autre bouton radio apparaît plus haut dans la page (c'est arrivé avec les modes de filtre). Correction : `app.radio(key="workflow_step")`.

#### f) Classes : où elles seraient utiles

| Candidat | Verdict | Raison |
|---|---|---|
| **Plan de nettoyage** (`pipeline`, 10 paramètres ; dict `config` stocké en session et dans la recette) | **Oui** : `@dataclass CleaningPlan` (règles, espaces, doublons, politique de conversion, règles de rejet, note, responsable) avec `to_dict()` | Regroupe un état cohérent ; supprime la signature à 10 paramètres. **Contrainte** : `to_dict()` doit produire exactement le même JSON qu'aujourd'hui (recette, rapport). |
| **Spécification de graphique / filtre** (dicts validés par `validate_configuration`, 59 lignes) | **Possible, pas prioritaire** | Les dicts font le va-et-vient avec le JSON et la session. Des fonctions de validation par type (`validate_filter`, `validate_chart`) suffisent et découpent la fonction de 59 lignes sans changer le format. |
| **Règle de qualité** (`audit` : chaîne de `if` par type) | **Non** : une table `{type: fonction de détection}` suffit | Pas d'état propre au-delà du dict ; la table réduit la complexité sans hiérarchie de classes. |
| **État de session** (≈ 40 clés en chaînes, réinitialisations dispersées) | **Non** : un module `core/session.py` avec les noms de clés en constantes et 3 fonctions (`reset_project`, `invalidate_cleaning`, `reset_dashboard`) | Une classe enveloppant `st.session_state` ajouterait une couche sans bénéfice. |
| Diagnostic, statistiques, normalisation, dates, comparaison, répétitions, archive | **Fonctions** | Transformations sans état. |

### Décisions demandées avant l'étape 2

- **D1 – Commit de départ.** Commiter tel quel, sur `nettoyage`, `src/`, `docs/MISSIONS_MVP.md`, `docs/RAPPORT_MISSIONS.md`, `Dockerfile`, `compose.yaml` et `.dockerignore`. C'est indispensable pour `git mv` et pour un commit par étape. Les `__pycache__` sont déjà ignorés.
- **D2 – Champ « objectif » toujours vide** (a5). Je propose de le **garder**, pour ne pas changer les exports.
- **D3 – Noms Docker `itservice`.** Les renommer (nom de service, variable de port, README) ou les laisser ?
- **D4 – Suppressions de l'étape 2.**
  - Code : a3, a4, a6, a7 (corrige aussi la régression de performance).
  - Tests : `test_guided_workflow` (couvert par `test_missing_counts_are_visible_before_targeted_choices` et `test_sample_csv_through_all_steps`) et l'assertion de la ligne 128.
  - Réparation des tests fragiles (`radio[0]` → clé).
  - Renommage des données de test IT.
- **D5 – Test navigateur (étape 6).** Installer Playwright et Chromium (environ 150 Mo) : dans le `.venv` du projet, ou dans un environnement séparé hors du dépôt ? (Docker 29.0.1 est disponible pour la vérification Docker.)

### Décisions reçues et étape 2 (faite)

Décisions : D1 commit de départ ✔ · D2 champ « objectif » conservé (exports inchangés) · D3 noms Docker renommés ✔ · D4 suppressions appliquées ✔ · D5 Playwright 1.64.0 + Chromium 156 dans le `.venv` du projet ✔.

| Commit | Contenu | Vérifications |
|---|---|---|
| `cba2ec8` | État de départ (29 fichiers jamais suivis : `src/`, docs, Docker) | 54 tests OK |
| `8d4e236` | Étape 2 : code mort a3, a4, a6, a7 ; `test_guided_workflow` et l'assertion « Noter ce que » retirés ; navigation des tests par clé (26 `app.radio[0]`) ; données de test sans nom IT | 53 tests OK · application démarrée · **référence identique** (exemple et CSV réel) · interactions 0,2–0,4 s (au lieu de 0,3–0,6 s) |
| `887def1` | Docker : `itservice-analytics` / `itservice` / `ITSERVICE_PORT` → `analyse-csv` / `analyse` / `ANALYSE_PORT` (port 8503 inchangé) ; README | 53 tests OK · `docker compose config` valide |

Un conteneur de l'ancien projet (`itservice-analytics-itservice-1`) tourne encore sur le port 8503. Il devra être arrêté avant la vérification Docker de l'étape 6.

### Plan de restructuration (étape 3) — à valider

**Contraintes relevées dans le code :**
- Les règles de qualité (`audit`) servent aux étapes 2, 3, 4 et 6. Elles importent `infer_roles` (étape 5). → règles, dictionnaire et rôles vont dans `core/`.
- `quality_ui` (étape 2) importe `reset_dashboard` et `ROLES` (étape 5) ; `cleaning_ui` (étape 3) importe `invalidate_cleaning` (interface de l'étape 2). → réinitialisations et cache dans `core/session.py`.
- Le Dockerfile copie tout `src/` et lance `src/app.py` : aucun changement Docker nécessaire.

**Arborescence cible :**

```
src/
  app.py                     entrée Streamlit : page, barre latérale, navigation, appel des écrans
  config.py                  constantes nommées (5 000 points, 1 000 / 50 valeurs, 30 graphiques, 100 groupes, 200 caractères, 2 Mo, P1/P2/P3, largeurs, tris…)
  core/                      commun, sans Streamlit (sauf session.py)
    lecture.py               lecture CSV (en-tête, options)                    ← app.read_csv (sans le décorateur de cache)
    dictionnaire.py          initial_dictionary, normalize_missing, convert, records, TYPES   ← quality.py
    roles.py                 infer_roles, looks_like_iso_dates, ROLES, mots-clés              ← visualization.py
    statistiques.py          numeric_columns, statistics, profile, duplicate_rows, bornes de Tukey   ← analysis.py (+ doublon b4)
    regles.py                CHECKS, validate_rule, audit, recommendation, création de règle (b1)   ← quality.py
    session.py  [Streamlit]  cached, invalidate_cleaning, reset_dashboard, réinitialisation du projet   ← session_cache.py, quality_ui, dashboard, app
  etape1_decouverte/
    ecran.py                 import (barre latérale), relecture, avertissement d'effacement, aperçu   ← app.py
  etape2_exploration/
    diagnostic.py            diagnose                                           ← diagnostics.py
    repetitions.py           inspect_repetitions                                ← repetitions.py
    ecran.py                 explore + sections repliées                        ← app.py
    dictionnaire_ui.py       dictionary_editor, missing_marker_editor          ← quality_ui.py
    regles_ui.py             audit_editor                                       ← quality_ui.py
    repetitions_ui.py        repetition_editor                                  ← repetitions_ui.py
  etape3_nettoyage/
    pipeline.py              pipeline, clean                                    ← quality.py, analysis.py
    ecran.py                 cleaning_screen                                    ← cleaning_ui.py
  etape4_comparaison/
    comparaison.py           compare_audits, tableau avant/après                ← quality.py, app.py
    ecran.py                                                                    ← app.py
  etape5_visualisation/
    preparation.py           parse_dates, prepare                               ← visualization.py
    suggestions.py           suggestions
    filtres.py               apply_filters
    graphiques.py            chart_data
    configuration.py         validate_configuration
    ecran.py                 dashboard (orchestration)                          ← dashboard.py
    filtres_ui.py, rendu.py  filter_editor, render_chart                        ← dashboard.py
  etape6_synthese/
    rapport.py               construction du rapport JSON (sortie de app.py), project_archive   ← app.py, reporting.py
    ecran.py                 conclusions, décision, téléchargements, context()  ← app.py, quality_ui.py
  tests/                     miroir : tests/core/, tests/etape2_exploration/ … ; test_app.py (parcours complet) et fixtures/ à la racine
```

Sens des imports : `core` ← étapes ; une étape n'importe que `core`, `config` et des étapes **antérieures** (ex. l'étape 3 réutilise `missing_marker_editor` de l'étape 2 ; l'étape 6 réutilise `prepare` et `chart_data` de l'étape 5 pour l'archive).

**Ordre des commits** (tests, démarrage et comparaison à la référence entre chaque) :
1. `core/` + `config.py`
2. étape 5
3. étape 2
4. étape 3
5. étape 4
6. étape 6
7. étape 1 et allègement de `app.py`
8. tests en miroir

Les fichiers qui gardent leur contenu principal sont déplacés avec `git mv` : `session_cache.py`, `analysis.py`, `diagnostics.py`, `repetitions.py`, `repetitions_ui.py`, `cleaning_ui.py`, `dashboard.py`, `reporting.py`, `visualization.py`. Les fichiers éclatés (`quality.py`, `quality_ui.py`, `app.py`) sont déplacés vers leur destination principale, puis leurs autres parties sont extraites.

**Ce qui ne change pas :**
- les noms des fonctions publiques (`audit`, `pipeline`, `diagnose`…), les clés de session, les messages et les exports ;
- les commandes `python -m streamlit run src/app.py` et `python -m unittest discover -s src/tests` ;
- Docker.

Les noms des nouveaux fichiers sont en français ; les noms des fonctions restent ceux du code existant. L'étape 4 du cahier (classe de plan de nettoyage, découpage des fonctions longues, constantes) viendra **après** les déplacements, pour qu'aucun commit ne mélange déplacement et réécriture.

---

## Refonte pour analystes débutants — maquette (2026-10-22)

**Constat de l'utilisatrice :** la plateforme est trop compliquée et fatigante pour un analyste junior ou en apprentissage ; on ne sait pas clairement quoi faire, ni pour l'analyse ni pour les graphiques.

**Décisions :**
- Outil simple et compréhensible pour un analyste débutant.
- Le « mode expert » est laissé de côté pour le moment : dictionnaire détaillé, règles personnalisées, répétitions, configuration JSON.
- La décision formelle GO / GO avec réserves / NO-GO est retirée (jugée inadaptée).
- La restructuration du nettoyage (étape 3) est **en pause** : le code sera rangé directement selon le nouveau parcours une fois la maquette validée.

**Maquette cliquable** (4 écrans, vraies valeurs d'`exemple.csv`) : https://claude.ai/artifact/Y8ZtYetYmmA4G96anE1ZcQ

| Écran | Contenu |
|---|---|
| 1 · Importer | Fichier, confirmation « 7 lignes, 4 colonnes », aperçu ; options de lecture derrière « Le tableau ne ressemble pas à votre fichier ? » |
| 2 · Comprendre | 3 chiffres clés ; une carte par colonne (rôle en mots simples, % rempli, mini-graphique, point à vérifier, rôle modifiable) ; liste des 4 points à vérifier ; un « bon réflexe » pédagogique |
| 3 · Corriger | Une carte par problème : explication, lignes concernées, 2 ou 3 choix en un clic (par défaut : ne rien changer). Résultat recalculé en direct (lignes gardées / écartées, cases vides, montant moyen avant → après), message « Écarter n'est pas corriger », journal automatique |
| 4 · Visualiser et exporter | 3 graphiques prêts avec titres clairs et une phrase « À retenir » (y compris les mises en garde : moyenne sur 1 valeur, volume ≠ performance) ; ajout guidé par une question ; 3 téléchargements ; notes facultatives |

Le moteur actuel (calculs, rejets tracés, comparaison exclusion / correction) est réutilisé tel quel : seuls le parcours et les écrans changent.

**Maquette validée (2026-10-22).** Rôle de l'outil précisé par l'utilisatrice : les 4 étapes servent à **auditer et préparer la qualité des données avant de commencer l'analyse métier**. L'outil livre des données fiables et la trace de ce qui a été vérifié et décidé ; l'analyse métier se fait ensuite.

---

## Refonte — outil simple en 4 étapes : réalisation (2026-10-22)

Plan validé : les 4 étapes de la maquette, mode expert gardé à côté (code et tests conservés).
Branche `nettoyage`. Périmètre : `src/`, `compose.yaml`, docs ; notebooks, Power BI et données non touchés.

### Commits

| Commit | Contenu |
|---|---|
| `51b1d40` | Rangement de `src/` par étape (`git mv`, imports réécrits). Aucun changement de comportement : **résultats identiques à la référence** sur exemple.csv et sur le CSV réel. |
| `5bcef54` | Moteur du parcours simple : fiches de colonnes, 5 familles de points à vérifier, plan de nettoyage, résultat avant/après, journal en phrases, graphiques de contrôle et « À retenir », rapport qualité et archive. Extensions sans effet sur l'existant : traitement des textes invalides par colonne (`pipeline`), ordre jour/mois par colonne (`prepare`), codes « ? » exclus des « textes dans des nombres » (`diagnose`, option). |
| `7703c26` | Les 4 écrans (`etapeN_*/ecran.py`), navigation (`app.py`), thème (`src/.streamlit/config.toml`). Ancienne interface déplacée : `src/expert/app_expert.py`. |
| `ffaf8c2` | **Correction** : les téléchargements générés au clic ne produisaient aucun fichier (un clic relançait le script et annulait le fichier). Défaut présent depuis la mission 3, aussi dans le mode expert. Ajout du test navigateur. |

Au total, `src/` : 62 fichiers modifiés, +3 085 / −973 lignes.

### Règle de rangement

Une étape n'importe que `core/`, `config.py` et des étapes **antérieures**. Deux ajustements en cours de route pour la respecter :
- la lecture des dates passe dans `core/dates.py` ;
- la détection des points à vérifier passe dans l'étape 2 (Comprendre), car l'étape 3 (Corriger) applique les choix.

### Tests

**81 tests, tous OK** :

| Dossier | Tests |
|---|---|
| core | 15 |
| etape2_comprendre | 7 |
| etape3_corriger | 10 |
| etape4_visualiser | 19 |
| expert | 23 |
| parcours simple (AppTest) | 7 |

Couleurs des graphiques vérifiées avec le script de validation : bleu `#1F5FD1`, bleu moyen `#6A8FDB` pour une moyenne fragile, gris `#8A919C` pour « non renseignée ». Contraste ≥ 3:1 ; chaque barre porte sa valeur écrite.

### Test dans le navigateur (Chromium, Playwright)

Script : `src/tests/navigateur/parcours_navigateur.py`.

| Étape | Résultat |
|---|---|
| 1. Import (nom, lignes, colonnes, aperçu) | réussi |
| 2. Mauvais séparateur → message, puis correction | réussi |
| 3. Explorer (colonnes, doublons, bon réflexe) | réussi |
| 4. « ? » reconnu comme vide, traitement choisi | réussi |
| 5. Exclusion distinguée de la correction | réussi |
| 6. Graphiques de contrôle, ajout d'un graphique | réussi |
| 7. Chaque téléchargement (CSV, lignes écartées, rapport, ZIP) produit un fichier lisible ; fichier d'origine identique dans l'archive | réussi (après correction `ffaf8c2`) |
| 8. Réimport de la configuration JSON du dashboard | non applicable à l'outil simple (mode expert ; couvert par ses tests AppTest) |
| 9. Changement d'option de lecture après du travail → avertissement | réussi |

**CSV réel (141 712 × 36), dans le navigateur :**
- import 3,4 s ;
- arrivée sur Comprendre 5,4 à 7,8 s, arrivée sur Corriger 1,9 à 5,9 s (une seule fois, analyse du fichier) ;
- validation → graphiques 1,7 s ;
- **chaque interaction 0,3 à 0,4 s**.

**Docker** : image construite et lancée sur le port 8504. Le test navigateur complet réussit sur le conteneur, qui a ensuite été arrêté. L'ancien conteneur `itservice-analytics` (port 8503) n'a pas été touché.

### Ce qui n'a pas pu être vérifié / limites

- Le test navigateur n'est pas lancé par `unittest` : il demande un serveur et Chromium.
- Les mesures AppTest surestiment certains temps (jusqu'à 1,3 s) : ce sont les mesures du navigateur qui font foi.
- Le rendu sur téléphone n'a pas été testé.
- Le champ « objectif » du rapport du mode expert reste vide (décision D2 : exports inchangés).

---

## Mode expert léger (2026-10-22)

**Demande :** un mode expert clair, avec seulement ce qui est utile à un analyste junior, choisi par deux boutons « Mode simple » / « Mode expert ». Sans P1/P2/P3, JSON, expressions régulières ni GO/NO-GO. Maquette validée (deuxième rangée de la maquette).

**Réalisé (4 ajouts, uniquement visibles en mode expert) :**

| Étape | Ajout | Moteur réutilisé |
|---|---|---|
| Comprendre | Règles à cocher sur chaque carte : doit être remplie, valeurs uniques (identifiants), entre deux bornes (nombres) ; résultat immédiat | `audit` (contrôles Obligatoire, Unique, Intervalle) via `regles_simples` |
| Corriger | Carte « Règles non respectées » : garder et signaler / écarter ; les lignes signalées sont notées dans le journal et le rapport | `pipeline` (règles mises en rejet) |
| Corriger | Carte « Espaces en trop », seulement s'il y en a | `pipeline(trim=True)` |
| Visualiser | Filtre avant les graphiques : garder / exclure des valeurs d'une catégorie, période ; les fichiers téléchargés ne changent pas | `apply_filters` |

**Choix à signaler :**
- Pour la règle « entre deux bornes », un texte non numérique (« abc ») n'est pas compté comme hors limites. Il a déjà sa propre carte « texte dans des nombres » ; le compter deux fois aurait été déroutant. Une option `ignore_text` du contrôle « Intervalle » le permet ; l'ancienne interface experte garde son comportement.
- La carte « Espaces en trop » n'apparaît que si le fichier en contient (même logique que les autres points). La maquette la montrait toujours.
- Dans la doc et le code, l'ancienne interface (`src/expert/`) s'appelle désormais « ancienne interface experte (archive) », pour ne pas la confondre avec le nouveau bouton « Mode expert ».

**Vérifications :**
- **92 tests OK**, dont 11 nouveaux : 8 côté moteur (`test_expert.py`), 3 sur l'interface (`ModeExpertTests`).
- **Test navigateur** : 11 étapes réussies, dont E1 à E3 pour le mode expert (règle cochée, lignes écartées, filtre « 4 / 5 lignes retenues » sans changement des fichiers téléchargés).
- **Docker** reconstruit sur http://localhost:8503 ; le même test navigateur y réussit.

---

## Un seul parcours : règles facultatives et Filtrage (2026-10-22)

**Demande :** l'écran Corriger était trop chargé de texte et le fond blanc fatiguait les yeux. Il n'y avait presque pas de différence entre le mode simple et le mode expert aux étapes 1 à 3. La demande : renommer « Mode expert » en « Filtrage » et le réserver à l'étape 4, garder les règles à cocher (jugées importantes) dans le parcours, et retirer « Cette colonne contient », répété sous chaque carte.

**Réalisé :**

| Où | Changement |
|---|---|
| Toute l'application | Couleurs plus douces : fond gris-bleu (#F2F4F8), texte bleu-gris foncé (#2C3E50), bordures gris-bleu ; même bleu pour les boutons |
| Barre du haut | Boutons « Mode simple / Mode expert » retirés : un seul parcours |
| Comprendre | Bloc « Cette colonne contient » retiré ; un clic sur l'étiquette du type (« Catégorie »…) ouvre le choix pour le corriger. Règles à cocher dans un volet fermé « Règles (facultatif) » sur chaque carte |
| Corriger | Explication de chaque carte derrière l'icône (?) au lieu d'un paragraphe ; phrase sous les boutons retirée ; badge « Mode expert » retiré. Cartes « Règles non respectées » (si une règle cochée échoue) et « Espaces en trop » (si le fichier en contient) pour tout le monde |
| Visualiser | Interrupteur « Filtrage », éteint par défaut, qui affiche le filtre existant |
| Rapport qualité | Section « Règles vérifiées » (au lieu de « Règles vérifiées (mode expert) ») |

**Choix à signaler :**
- Le comptage des espaces en trop parcourt tout le fichier. Il est désormais mémorisé une fois par fichier, pour que les clics de l'étape Corriger restent rapides sur un gros CSV.
- Sur un fichier qui contient des espaces en trop, une carte de plus apparaît à l'étape Corriger. Par défaut elle ne change rien (« Laisser tel quel »).
- « Voir les lignes concernées » est gardé sur chaque carte de Corriger : il sert à vérifier avant de choisir.
- `test_expert.py` est renommé `test_regles_espaces.py`.

**Vérifications :**
- **92 tests OK** (tests de l'interface adaptés : `ReglesEtFiltrageTests`).
- **Test navigateur** : 12 étapes réussies, dont E0 (type changé par l'étiquette) et E3 (Filtrage éteint par défaut, « 4 / 5 lignes retenues », téléchargements inchangés).

---

## Mission 7 — Répétitions, version légère (2026-10-22)

**Objectif du cahier :** diagnostic générique des répétitions : clé de regroupement choisie par l'utilisateur, groupes, colonnes qui varient, enregistrements sources. Ne jamais conclure qu'un identifiant répété est une erreur. Le diagnostic ne modifie ni les données ni le nettoyage.

**Pourquoi c'est utile :** l'outil signalait « « 004 » apparaît 2 fois » et traitait les lignes strictement identiques, mais ne disait pas *ce qui change* quand un identifiant se répète. Dans un journal d'événements, un même incident a une ligne par mise à jour : sans cette information, un analyste débutant risque de prendre ces lignes pour des doublons et de les écarter.

**Réalisé :**

| Où | Ce qui est montré |
|---|---|
| Comprendre, carte d'une colonne Identifiant qui se répète | Volet fermé « Pourquoi « … » se répète ? », calculé seulement à l'ouverture |
| Dans le volet | Les colonnes qui changent entre les lignes d'une même valeur, avec la part des groupes où elles changent (8 premières) ; les colonnes toujours identiques ; un exemple (la valeur la plus répétée, 20 premières lignes, colonnes qui changent seulement, numéros de ligne d'origine) ; la phrase « Une valeur répétée n'est pas forcément une erreur » |
| Copies exactes | Renvoi vers la carte « Des lignes identiques » de l'étape Corriger |

- La clé est la colonne de la carte : l'utilisateur la choisit en lui donnant le type « Identifiant ».
- Une case vide face à une valeur compte comme un changement. Une part arrondie n'affiche « 100 % » que si la colonne change dans tous les groupes.
- Code : `etape2_comprendre/repetitions.py` (fonction `variations`, en lecture seule).

**Sur le fichier réel (141 712 lignes, colonne `number`) :** 24 918 identifiants se répètent, c'est-à-dire toutes les lignes. `incident_state`, `active` et `sys_mod_count` changent dans 100 % des groupes, `sys_updated_at` dans 99 %. `opened_at`, `opened_by`, `closed_code` et `resolved_at` sont identiques dans tous les groupes. Cela décrit un journal d'événements, pas des doublons. Calcul : environ 0,5 s ; ouverture du volet dans le navigateur : 1,6 s.

**Hors de cette version (reste dans l'ancienne interface experte) :** clé composée, colonnes de détail, export JSON des groupes.

**Vérifications :**
- **95 tests OK**, dont 3 nouveaux (`test_repetitions.py`) et l'ouverture du volet dans `test_app.py`.
- **Test navigateur** : 13 étapes sur l'exemple, dont E0b (volet des répétitions), et le parcours complet sur le fichier réel réussis.

---

## Design « Sarcelle qualité » et logo (2026-10-23)

**Demande :** un design moins neutre, avec des couleurs adaptées à un outil d'analyse professionnel, un logo, et des couleurs de graphiques bien visibles. Maquette avec trois ambiances (Bleu confiance, Indigo analyse, Sarcelle qualité) : l'option C est retenue.

**Réalisé :**

| Élément | Avant | Après |
|---|---|---|
| Couleur principale (boutons, étape en cours, choix sélectionné) | bleu `#1F5FD1` | sarcelle `#0B6F71` |
| Fond de page | gris-bleu `#F2F4F8` | sarcelle très clair `#F1F5F5` |
| Cartes et chiffres clés | même couleur que le fond | blanches, pour se détacher du fond |
| Graphiques : valeurs fiables / moyennes fragiles / cases vides | `#1F5FD1` / `#6A8FDB` / `#8A919C` | `#0F8B8D` / `#62B2B4` / `#B4BAC2`, fond transparent |
| En-tête | texte « Analyse simple · audit qualité… » | logo `src/assets/logo.svg` : carré sarcelle, trois barres et une coche, nom et sous-titre |

**Choix à signaler :**
- Les couleurs des graphiques ont été vérifiées avec un outil de contrôle : contraste sur fond blanc, et différence visible même pour les personnes daltoniennes. Le gris des cases vides a été éclairci pour se distinguer de la sarcelle ; il reste lisible parce que chaque barre affiche son libellé et sa valeur.
- Le thème de Streamlit ne colore pas les cartes : chaque carte encadrée reçoit une clé `carte_…`, et une ligne de style dans `app.py` les rend blanches. Aucune autre règle de style n'est ajoutée.
- Orange (alertes) et vert (confirmations) restent réservés aux messages et ne sont pas utilisés dans les graphiques.

**Vérifications :** 95 tests OK ; test navigateur de 13 étapes réussi en local et sur Docker ; captures des 4 étapes comparées à la maquette.

