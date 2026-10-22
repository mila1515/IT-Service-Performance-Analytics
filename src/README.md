# Analyse simple — audit qualité d'un CSV avant l'analyse métier

Outil pour analyste débutant ou en apprentissage : importer n'importe quel fichier CSV,
comprendre ce qu'il contient, corriger les problèmes de forme en un clic, contrôler le
résultat en graphiques et remettre des données fiables avec la trace de ce qui a été décidé.
L'analyse métier vient ensuite. Indépendant des notebooks et de Power BI.

Depuis la racine du projet, dans l'environnement virtuel :

```powershell
python -m pip install -r src/requirements.txt
python -m streamlit run src/app.py
```

## Les 4 étapes

1. **Importer** : déposer le fichier ; nombre de lignes et de colonnes, aperçu. Aucune saisie
   obligatoire. Options de lecture (séparateur, encodage, décimales) repliées derrière « Le tableau
   ne ressemble pas à votre fichier ? ». Les identifiants (001…) sont lus en texte pour garder
   leurs zéros. Changer une option après des choix les efface, avec un avertissement.
2. **Comprendre** : chiffres clés, une carte par colonne (rôle en mots simples, remplissage,
   mini-graphique, rôle modifiable), liste des points à vérifier. Rien n'est modifié.
3. **Corriger** : une carte par famille de points — codes de valeur manquante (« ? », « NA »…),
   texte dans des nombres, cases vides, lignes identiques, dates ambiguës (jour/mois). Chaque
   point se règle en un clic ; **par défaut, rien ne change**. Le résultat (lignes gardées et
   écartées, cases vides, moyenne avant → après) et le journal se mettent à jour en direct.
   Une ligne écartée n'est pas effacée et « écarter n'est pas corriger » est rappelé.
4. **Visualiser et exporter** : trois graphiques de contrôle choisis selon les rôles, chacun avec
   une phrase « À retenir » (règles générales : valeur la plus fréquente, moyenne fragile sous
   3 valeurs, volume ≠ performance, textes ignorés signalés) ; ajout guidé par une question ;
   téléchargements générés au clic : données corrigées (CSV), lignes écartées (CSV, numéro de
   ligne d'origine et raison), rapport qualité (Markdown), archive ZIP avec le fichier d'origine
   inchangé et le journal.

## Mode simple / Mode expert

Deux boutons en haut de l'écran. **Mode simple** (par défaut) : le parcours ci-dessus.
**Mode expert** : quatre ajouts seulement, pensés pour un analyste junior.

1. **Comprendre** : sur chaque carte, des règles simples à cocher — « doit être remplie »,
   « valeurs uniques » (identifiants), « valeurs entre deux bornes » (nombres). Le résultat
   s'affiche aussitôt (lignes qui ne respectent pas).
2. **Corriger** : une carte « Règles non respectées » : garder et signaler, ou écarter les lignes.
   Une règle non respectée n'est pas forcément une erreur ; les textes non numériques ne sont
   pas comptés dans les bornes (ils ont déjà leur propre carte).
3. **Corriger** : une carte « Espaces en trop » quand des textes en ont (« A » et « A␣ »).
4. **Visualiser** : un filtre avant les graphiques (garder ou exclure des valeurs d'une
   catégorie, choisir une période). Il ne change pas les données téléchargées.

Le rapport qualité indique alors chaque règle vérifiée. Volontairement absents : priorités
P1/P2/P3, seuils en %, expressions régulières, clés composées, configuration JSON, GO/NO-GO.

Règles constantes : le fichier d'origine n'est jamais modifié ; chaque traitement repart de
lui ; moyenne et médiane seulement pour les nombres, « Inconnu » seulement pour les
catégories ; aucune règle métier ni colonne propre à un domaine ; le rapport ne certifie pas
l'exactitude des valeurs. Les sessions restent en mémoire : télécharger avant de fermer.

## Lancer avec Docker Desktop

Depuis la racine du dépôt :

```powershell
docker compose up -d --build
```

Ouvrir **http://localhost:8503**. Le port est exposé uniquement sur la machine
locale. Les données, notebooks et fichiers Power BI du dépôt ne sont pas copiés
dans l'image. Importer le CSV depuis l'interface.

```powershell
docker compose ps
docker compose logs --tail 50 analyse
docker compose down
```

Pour utiliser un autre port disponible :

```powershell
$env:ANALYSE_PORT = "8504"
docker compose up -d --build
```

Après une modification du code, relancer `docker compose up -d --build`.
Les sessions restent en mémoire : exporter le projet avant d'arrêter ou de

## Organisation du code

```
src/
  app.py                 navigation entre les 4 étapes (point d'entrée)
  config.py              constantes (seuils, couleurs, limites d'affichage)
  .streamlit/config.toml thème
  core/                  commun : lecture, dictionnaire, rôles, dates, statistiques, règles,
                         textes, dessin des graphiques, session (seul module Streamlit)
  etape1_importer/       écran d'import
  etape2_comprendre/     fiches de colonnes, diagnostic, détection des points + écran
  etape3_corriger/       pipeline, application des choix, résultat, journal + écran
  etape4_visualiser/     préparation, graphiques de contrôle, exports + écran
  expert/                ancienne interface experte, gardée comme archive (voir plus bas)
  tests/                 tests en miroir ; tests/navigateur/ : parcours dans Chromium
```

Une étape n'importe que `core/`, `config.py` et des étapes antérieures ; le calcul (sans
Streamlit) est séparé des écrans (`ecran.py`).

## Vérifications

- Tests : `python -m unittest discover -s src/tests` (depuis la racine).
- Navigateur : voir `src/tests/navigateur/README.md`.

## Limites

Un seul fichier CSV, traitement en mémoire, pas de restauration d'une session. Pas d'import
Excel ni de base de données. Les graphiques servent au contrôle, pas aux conclusions métier.
La première arrivée sur les étapes 2 et 3 prend quelques secondes sur un gros fichier
(environ 5 s pour 141 712 lignes × 36 colonnes) ; ensuite chaque interaction prend ~0,3 s.

## Ancienne interface experte (archive)

À ne pas confondre avec le bouton « Mode expert » ci-dessus. L'ancienne interface complète en
6 étapes reste disponible à part, pour mémoire :
dictionnaire détaillé, règles de qualité P1/P2/P3 rejouées avant/après, diagnostic des
répétitions, dashboard configurable (filtres, disposition, configuration JSON), décision GO /
NO-GO. Code et tests dans `src/expert/` et `src/tests/expert/`.

```powershell
python -m streamlit run src/expert/app_expert.py
```

Parcours : découverte du CSV, exploration brute et statistiques, nettoyage avec
prévisualisation et validation, comparaison avant/après, exploration nettoyée et
visualisation, conclusions et export CSV/JSON.

Les cellules vides restent vides par défaut. Les décisions sont prises par colonne.
Les remplacements moyenne/médiane sont réservés aux mesures numériques.
Les lignes mises en rejet sont exclues avant le calcul des remplacements.
Les doublons supprimés sont uniquement les lignes strictement identiques.
Les données brutes restent intactes. Chaque nouveau traitement repart du brut.
Le rapport JSON exporte la configuration, l'historique et les notes métier.

Limites de cette première version : une seule source CSV, traitement en mémoire,
sans restauration automatique d'une session complète. Une archive ZIP permet de
conserver le projet et les versions validées. Les formats de date et les types
sont définis par l'utilisateur dans le dictionnaire. Pas encore de connexion SQL, import Excel,
ni de mapping ou d'indicateur métier calculé automatiquement. Les valeurs
extrêmes sont signalées avec la règle IQR et conservées. Les statistiques utilisent
les valeurs renseignées ; écart-type et variance utilisent n − 1.

Vérifications : `python -m unittest discover -s src/tests`.

Performances : les diagnostics, audits, statistiques et préparations de graphiques
sont mémorisés pour la session et recalculés seulement si les données, le
dictionnaire, les règles ou les rôles changent. Les fichiers à télécharger sont
générés au clic.

### Dashboard adaptable aux données

À l'étape 5, confirmer les rôles des colonnes : mesure, catégorie, date ou
identifiant. Les identifiants sont exclus des suggestions d'agrégation.
Les rôles proposés sont des heuristiques, toujours corrigeables, initialisés depuis
le dictionnaire de l'étape 2. Identifiant : un mot du nom parmi `id`, `uuid`, `code`,
`number`, `num`, `no`, `n°`, `numéro`, `matricule`, `identifiant`, `réf`, `référence`, `clé`.
Date : nom contenant `date` (hors `update`), finissant par `_at`, mots `horodatage`,
`timestamp`, ou valeurs toutes au format ISO `AAAA-MM-JJ[ hh:mm[:ss]][fuseau]`.
Une année numérique au rôle Date est lue comme une année. Un seul format de date
est appliqué par colonne ; les valeurs qui ne le respectent pas sont signalées. Les dates ambiguës
nécessitent de confirmer le choix jour/mois. Les conversions ne modifient pas
les données nettoyées ; les échecs sont comptabilisés comme valeurs manquantes
dans la vue de visualisation. Les dates avec fuseau sont ramenées en UTC.

Suggestions expliquées : histogramme, boîte à moustaches, barres, évolution
temporelle, nuage de points et tableau croisé des effectifs (au format long).
L'éditeur permet de choisir les axes, l'effectif / somme / moyenne / médiane,
la période, le titre, le tri et la limite de groupes affichés.

Les filtres globaux s'appliquent à tous les graphiques après clic sur
« Appliquer les filtres globaux ». Des filtres locaux peuvent ensuite être
ajoutés à chaque graphique ; les deux niveaux sont combinés par intersection.
Catégories : mode « Retenir » ou « Exclure » les valeurs choisies. Jusqu'à 50
valeurs distinctes, toutes sont retenues par défaut ; au-delà, le mode « Exclure »
avec une sélection vide garde toutes les lignes. Au-delà de 1 000 valeurs distinctes
(identifiants), les valeurs se saisissent une par ligne. Nombres : bornes inclusives. Dates : période
inclusive, y compris toute la dernière journée. Chaque filtre permet de retenir
ou d'exclure les valeurs manquantes. Les effectifs retenus et les lignes non
exploitables pour le graphique sont affichés.

Prévisualiser puis ajouter un graphique au dashboard. Les graphiques s'affichent
dans l'ordre de la liste : la section de disposition change la position (1 = en haut)
et la largeur (demi / pleine), ou retire un graphique. Deux demi-largeurs consécutives
partagent une rangée ; une pleine largeur occupe sa propre rangée. « Modifier ce
graphique » ouvre son titre, son calcul et ses filtres dans l'éditeur. Les anciennes
configurations JSON avec un numéro de ligne (« row ») sont acceptées : leurs graphiques
sont rangés par ligne à l'import. Pas de glisser-déposer dans cette version.
Maximum : 30 graphiques et 100 groupes par graphique en barres.

Exporter / réimporter la configuration JSON depuis l'étape 5. Les colonnes,
leurs rôles et le format des dates doivent correspondre à la configuration.
Une importation remplace le dashboard courant après validation. Une modification
des rôles ou du format des dates réinitialise le dashboard. Un nouvel import CSV
réinitialise toute la session. Les traitements de nettoyage recalculent les
graphiques existants sur les nouvelles données validées.

Les histogrammes et quartiles utilisent toutes les valeurs exploitables.
Au-delà de 5 000 points, les nuages affichent un échantillon reproductible ; les
boîtes affichent au maximum 1 000 valeurs hors moustaches, avec mention explicite.
Les courbes dépassant 5 000 périodes proposent le tableau complet et demandent
de réduire la période ou filtrer avant affichage. Une somme sur une période vide
reste manquante plutôt que de suggérer une observation à zéro.
Les suggestions sont fondées sur des règles, sans LLM, et ne remplacent pas la
validation métier des calculs. Aucun indicateur métier n'est déduit automatiquement.

Chaque graphique affiche le nombre de lignes retenues par ses filtres sur la base
des lignes après filtres globaux, et les lignes sans valeur exploitable.

### Parcours essentiel de qualité des données

1. **Découverte du CSV** : fichier, dimensions et premières lignes immédiatement
   visibles, sans champ de saisie à remplir. Aucune connaissance préalable du
   grain, de la période ou des indicateurs n'est exigée.
2. **Exploration brute** : statistiques, échantillon reproductible, dictionnaire
   éditable et diagnostic qualité. Dans le dictionnaire : définition, type observé
   et attendu, rôle, unité, champ obligatoire, unicité, criticité et faux vides.
   Des règles supplémentaires couvrent les bornes numériques, catégories permises,
   formats et ordre entre deux dates, avec seuil toléré et priorité P1/P2/P3.
   Les constats chiffrés sont affichés automatiquement, sans formulaire de notes
   à remplir pendant l'exploration. Les informations métier facultatives restent
   disponibles uniquement dans la synthèse.
3. **Nettoyage** : diagnostic chiffré avant les choix, responsable et note facultatifs, conversions réelles dans les données
   exportées, traitement des échecs (bloquer par défaut / rejeter / convertir en vide),
   choix par colonne pour les manquants, normalisation des espaces, doublons stricts
   et sélection de règles dont les échecs doivent être mis en rejet. Prévisualisation
   des données, rejets et contrôles avant validation.
4. **Comparaison** : règles rejouées avant/après, anomalies restantes, rejets,
   journal horodaté en UTC et nombre de versions validées. Pour chaque règle, les
   anomalies disparues sont séparées en « écartées par exclusion de lignes » (rejets :
   ce n'est pas une correction), « résolues sur lignes conservées » et « nouvelles
   anomalies ». Sans règle définie, l'étape l'indique : rien ne certifie les données.
5. **Analyse et visualisation** : dashboard configurable existant.
6. **Synthèse** : évaluation des règles et décision utilisateur GO / GO avec réserves /
   NO-GO, justification, conclusions et exports. Sans justification, la décision
   exportée reste « À évaluer ». Sans règle, aucun GO automatique n'est proposé.
   Un contrôle P1 en échec suggère NO-GO ; la décision finale appartient à l'utilisateur.
   Les informations de projet et la décision métier à éclairer peuvent être
   renseignées ici après lecture des résultats, sans bloquer les étapes précédentes.

À l'import, sélectionner les identifiants/codes dans « Colonnes à lire comme texte »
pour préserver leurs zéros initiaux. Seules les cellules vides sont interprétées
comme manquantes par le lecteur CSV ; les espaces seuls sont reconnus lors de
l'audit/nettoyage. Les chaînes NA, NULL, Inconnu, etc. restent des valeurs jusqu'à
leur déclaration explicite comme marqueurs, colonne par colonne.

Les dates sont lues en ISO 8601 sauf format explicitement défini, par exemple
`%d/%m/%Y %H:%M`. Les fuseaux sont convertis en UTC. Les valeurs infinies ne sont
pas acceptées lors d'une conversion numérique. Une valeur atypique reste conservée
tant qu'aucun traitement ou rejet explicite ne la concerne.

La référence d'un rejet/anomalie est le numéro d'enregistrement dans le CSV source
(à partir de 1, hors en-tête). Un enregistrement avec plusieurs motifs n'apparaît
qu'une fois dans les rejets, avec tous ses motifs. Le CSV des rejets utilise deux
lignes d'en-tête afin de séparer les métadonnées des colonnes originales.

L'archive ZIP contient le CSV original inchangé, les données nettoyées, les rejets,
le rapport JSON et sa synthèse Markdown, les résultats tabulaires du dashboard et
chaque version de nettoyage validée avec sa recette et son journal. Télécharger
l'archive avant de fermer la session ou de charger une autre source. Les versions
sont indépendantes et calculées depuis le brut, pas en cumulant les nettoyages.
Modifier le dictionnaire ou les règles invalide le nettoyage courant et sa décision,
sans effacer les versions déjà validées. Modifier le dictionnaire réinitialise aussi
le dashboard pour éviter des agrégations fondées sur d'anciens rôles.

Les seuils d'anomalies utilisent toutes les lignes comme dénominateur. L'unicité
signale toutes les occurrences renseignées d'une valeur dupliquée. Les contrôles
de format, type, intervalle, catégories et dates ignorent les valeurs manquantes :
les combiner avec un contrôle « Obligatoire » si nécessaire. Le rapport doit être
interprété selon les règles effectivement définies : il ne certifie pas l'exactitude
métier. Les obligations conditionnelles, la fraîcheur automatisée, la modélisation,
les jointures et les imports de plusieurs CSV restent hors périmètre pour le moment.

### Comprendre les répétitions sans imposer de métier

Dans l'étape 2, la section « Comprendre les clés répétées » est facultative.
Choisir une clé de regroupement simple ou composée, puis éventuellement des
colonnes distinguant les lignes / événements et les champs à comparer. Aucun
nom de colonne ni domaine n'est imposé : commande + ligne, circulation + date +
arrêt, employé + période + affectation sont des exemples de configurations.

Le diagnostic affiche les groupes répétés, les doublons stricts en excès,
les différences pour une même clé de ligne et les détails incomplets. Chaque
groupe est consultable avec les enregistrements sources et les colonnes qui
varient. Les champs non sélectionnés pour comparaison ne créent pas de conflit ;
les doublons stricts sont toujours évalués sur toutes les colonnes originales.
Les clés de regroupement incomplètes sont présentées à part. Les marqueurs vides
du dictionnaire sont reconnus, sans conversion de type ou normalisation du texte.
Une configuration modifiée reste un brouillon jusqu'au clic sur « Analyser les
répétitions ». Les résultats et paramètres sont exportables en JSON et inclus
dans le rapport et l'archive du projet si une analyse a été configurée.

Cette exploration ne modifie ni le nettoyage, ni les filtres, ni les contrôles
existants. Des détails distincts ne garantissent pas la validité métier ; des
lignes identiques ne sont pas une preuve suffisante d'erreur. Il n'y a ni fusion,
ni suppression, ni rejet automatique à partir de ce diagnostic.

Pour contrôler réellement une clé composée, confirmer explicitement son unicité
et ajouter la règle depuis cette section. Ce choix invalide le nettoyage courant
afin que les contrôles soient rejoués ; les versions validées restent conservées.
La règle signale toutes les occurrences d'une combinaison complète dupliquée.
Les clés incomplètes sont exclues de ce contrôle d'unicité : définir aussi des
contrôles « Obligatoire » pour les colonnes requises. Un éventuel rejet doit être
sélectionné explicitement à l'étape de nettoyage et porte alors sur toutes les
occurrences signalées, sans choisir arbitrairement une ligne à conserver.
Une nouvelle source CSV réinitialise la configuration et ces règles comme les
autres paramètres du projet.

### Interface simplifiée : observer avant de décider

Les étapes se suivent avec des boutons « Explorer les données », « Continuer vers
le nettoyage », « Continuer vers les graphiques » et « Passer à la synthèse ».
La navigation latérale reste disponible. La validation d'un nettoyage ouvre
directement la comparaison avant/après.

L'exploration présente d'abord les valeurs manquantes (effectifs, pourcentages,
lignes concernées), les doublons, les statistiques et distributions. Les types,
le dictionnaire, les règles métier et les clés répétées restent dans des sections
repliées. Les options de lecture du CSV sont également repliées.

Avant tout choix de nettoyage, un diagnostic affiche le nombre de cellules vides,
de lignes concernées et de doublons, puis un tableau par colonne : vides détectés,
pourcentages, échecs de conversion et moyenne/médiane pour les mesures numériques.
Seules les colonnes concernées disposent d'un choix de remplacement. Les valeurs
des colonnes complètes sont conservées sans poser de question. Les échecs de
conversion restent bloqués tant qu'aucun traitement explicite n'est choisi.

Les marqueurs possibles (`?`, `NA`, `NULL`, etc.) sont comptés séparément : ils
ne sont pas automatiquement considérés comme vides. Un bouton permet de les
reconnaître explicitement dans les colonnes du tableau ; ce choix est enregistré
dans le dictionnaire. Pour un traitement limité à certaines colonnes, utiliser
le dictionnaire. Cette distinction est utile lorsque les champs absents sont
représentés par un code comme `?` plutôt que par une cellule vide.

Le responsable et la note de nettoyage sont facultatifs. Sans note saisie, une
description automatique du plan est enregistrée dans le journal. La prévisualisation
montre les lignes conservées, vides restants et rejets ; les paramètres et contrôles
détaillés sont repliés. Chaque suppression ou remplacement reste un choix explicite.

Le dashboard propose un premier graphique adapté sans nécessiter de configuration.
L'aperçu précède l'ajout au dashboard ; les réglages d'axes, calculs, titre et
filtres locaux se trouvent dans « Personnaliser le graphique et ses filtres ».
La décision formelle GO/NO-GO est facultative et repliée dans la synthèse.
