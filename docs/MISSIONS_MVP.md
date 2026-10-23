# Analyse de données (MVP) — Cahier des missions

Tu interviens sur un projet appelé « Analyse de données (MVP) » : une application Streamlit qui sert de trame d'analyse pour un data analyst, utilisable sur n'importe quel fichier CSV. Ce n'est pas un projet de notebooks et ce n'est pas un projet de modélisation.

Réponds en français. Garde le code, les noms de fonctions et les messages d'interface en français, comme dans le code existant.

══════════ 1. OBJECTIF ══════════

Un analyste importe un CSV dont il ne connaît pas encore le contenu et suit ce parcours :
importer → explorer → diagnostiquer → nettoyer → contrôler → visualiser → exporter.

L'outil doit :
- montrer les informations avant de demander une décision ;
- ne demander aucune saisie obligatoire avant que l'utilisateur ait vu son fichier ;
- automatiser les observations et la traçabilité ;
- laisser à l'utilisateur toute décision qui change le sens ou le contenu des données ;
- fonctionner sur tout domaine (ventes, RH, ferroviaire, maintenance, IT...) sans colonne imposée ni règle métier cachée.

══════════ 2. STRUCTURE DU PROJET ══════════

- analysis.py : moteur, sans aucune dépendance à Streamlit, testable seul.
- app.py : interface Streamlit, six onglets (Importer, Explorer, Nettoyer, Contrôler, Visualiser, Exporter).
- tests/test_analysis.py : tests unittest du moteur.
- requirements.txt : streamlit, pandas, altair.
- README.md.

Principe : toute logique de calcul ou de transformation va dans analysis.py. app.py ne contient que de l'affichage et de l'état de session.

══════════ 3. ÉTAT ACTUEL (lis les fichiers pour le confirmer) ══════════

Fait et testé (moteur, 12 tests unittest qui passent) :
- lecture CSV avec séparateur, encodage, décimal, colonnes gardées en texte ;
- détection d'un séparateur probablement faux (une seule colonne lue) ;
- propositions de rôles (mesure, categorie, date, identifiant) ;
- profil des colonnes, statistiques des mesures et des catégories, valeurs atypiques (IQR) signalées ;
- diagnostic séparant cellules vides et marqueurs possibles (« ? », « NA », « NULL »...) ;
- doublons stricts ;
- nettoyage qui repart toujours du brut, avec journal, rejets (valeurs d'origine, ligne du CSV source, motifs) ;
- conversions impossibles bloquées par défaut (options : rejeter, convertir en vide) ;
- agrégations (effectif, somme, moyenne, médiane), évolution mensuelle ;
- export ZIP.

Écrit mais JAMAIS exécuté (interface) :
- tout app.py : il a été vérifié pour sa syntaxe seulement. Des erreurs au lancement sont probables.

Pas encore disponible (ne le présente jamais comme existant) :
- règles de qualité configurables avec seuils et priorités P1/P2/P3 ;
- filtres globaux et filtres locaux par graphique ;
- ordre et largeur des graphiques dans le dashboard ;
- détection automatique du séparateur ;
- diagnostic générique des répétitions (clé composée) ;
- restauration automatique d'une session complète ;
- plusieurs CSV, jointures, Excel, bases de données, modélisation, LLM.

══════════ 4. RÈGLES DE TRAVAIL ══════════

1. Propose un plan court avant de modifier du code, puis attends ma validation. Une tâche à la fois.
2. Ne modifie jamais les données brutes : chaque nettoyage repart de df_brut.
3. Ajoute ou mets à jour des tests pour toute transformation que tu ajoutes ou modifies, puis exécute : python -m unittest discover -s tests -v
4. Lance l'application (streamlit run app.py) et vérifie que chaque onglet s'affiche sans exception avant de déclarer une tâche terminée.
5. Ne change pas ce qui fonctionne sans raison, et dis-moi explicitement ce que tu as changé et pourquoi.
6. N'invente aucune règle ni interprétation métier. Si le sens d'une colonne est ambigu, l'utilisateur décide.
7. Distingue toujours ce qui est fait, ce qui est testé et ce qui est prévu.
8. Si une consigne est ambiguë, pose une seule question, après avoir proposé une réponse par défaut.

══════════ 5. COMPORTEMENTS À PRÉSERVER ══════════

Import
- Après import : nom du fichier, nombre de lignes, nombre de colonnes, aperçu lisible. Aucune saisie obligatoire.
- Options de lecture repliées. Message clair si un mauvais séparateur donne une seule colonne.

Exploration (avant tout nettoyage)
- Dimensions, échantillon reproductible (random_state=42), types, valeurs distinctes, vides, doublons stricts.
- Mesures : effectif renseigné, moyenne, médiane, min, max, quartiles, variance, écart-type.
- Catégories : valeurs distinctes, fréquences, catégories dominantes.
- Valeurs atypiques signalées, jamais supprimées automatiquement.
- Une colonne numérique n'est pas toujours une mesure (identifiant, code postal) : les rôles restent corrigeables.

Nettoyage
- Le diagnostic chiffré s'affiche avant les choix.
- Les marqueurs possibles (« ? », « NA »...) restent des valeurs tant que l'utilisateur ne les a pas confirmés comme vides.
- Les choix de remplacement n'apparaissent que pour les colonnes concernées. Moyenne et médiane seulement pour une mesure numérique ; « Inconnu » seulement pour une catégorie ; jamais pour un identifiant ou une date.
- Les doublons stricts ne sont pas écartés par défaut : des lignes identiques ne sont pas forcément des erreurs.
- Le journal se remplit automatiquement. Aucune justification écrite n'est obligatoire.
- Aperçu avant validation : lignes conservées, lignes écartées, valeurs manquantes restantes.

Contrôle
- Tableau avant/après, anomalies restantes, effet sur moyennes et médianes.
- Une baisse d'anomalies due à des exclusions n'est pas une correction : l'interface le dit.
- Barrière qualité obligatoire avant l'onglet Visualiser.
- Aucune règle de qualité n'est définie : l'interface ne présente jamais les données comme certifiées fiables.

Visualisation
- Graphiques proposés selon les rôles : distribution, effectifs par catégorie, comparaison entre groupes, évolution dans le temps, nuage de points.
- Toujours afficher les effectifs retenus, les exclusions dues aux valeurs manquantes et tout échantillonnage d'affichage.
- Ne pas confondre corrélation et causalité, absence de données et valeur zéro, volume d'activité et performance.

Export
- Données nettoyées, rejets, journal, diagnostic initial, configuration JSON du dashboard, archive ZIP (avec le CSV brut).
- Les sessions sont en mémoire : le dire clairement.

══════════ 6. MISSION 1 : STABILISER (aucune nouvelle fonctionnalité) ══════════

a) Installe les dépendances et lance les tests du moteur.
b) Lance l'application et parcours les six onglets avec un petit CSV d'exemple que tu crées dans un dossier de test (colonnes : id texte, catégorie avec des « ? », mesure avec une valeur non numérique, date, un doublon strict).
c) Liste toutes les erreurs, avertissements et comportements douteux, SANS rien corriger.
d) Vérifie en particulier :
   - st.dataframe(use_container_width=True) : paramètre peut-être déprécié dans la version de Streamlit installée ;
   - agreger() échoue si la colonne de regroupement s'appelle « valeur » ;
   - noms de colonnes contenant un point ou des caractères spéciaux dans les graphiques Altair ;
   - une colonne au rôle « date » qui est numérique (par exemple une année) ;
   - les widgets dont l'état est supprimé par reinitialiser() lors d'un nouvel import ;
   - la lenteur : le diagnostic et les statistiques sont recalculés à chaque interaction (pense à st.cache_data).
e) Rends-moi un rapport : problème, gravité (bloquant / gênant / mineur), correction proposée. Attends ma validation avant de corriger.

══════════ 7. MISSIONS SUIVANTES (une à la fois, dans cet ordre) ══════════

2. Correction des problèmes validés, avec tests.
3. Test de charge : si j'ajoute data/raw/incident_event_log.csv (environ 141 000 lignes, 36 colonnes, « ? » très fréquent pour les valeurs absentes), mesure le temps de chaque onglet et propose des optimisations (cache, limites d'affichage).
4. Filtres : filtres globaux et filtres locaux par graphique, combinés par intersection, avec effectifs retenus affichés.
5. Dashboard : choix de l'ordre, demi-largeur ou pleine largeur, modification d'un graphique existant.
6. Règles de qualité simples : complétude et unicité d'abord, avec seuil et priorité P1/P2/P3, rejouables avant/après nettoyage. Un résultat conforme prouve seulement que les règles définies sont respectées.
7. Diagnostic générique des répétitions : clé de regroupement choisie par l'utilisateur, groupes, colonnes qui varient, enregistrements sources. Ne conclus jamais automatiquement qu'un identifiant répété est une erreur. Le diagnostic seul ne modifie ni les données ni le nettoyage.

══════════ 8. CRITÈRES D'ACCEPTATION D'UNE TÂCHE ══════════

Une tâche est terminée seulement si :
- les tests unittest passent, y compris les nouveaux ;
- l'application se lance et les six onglets s'affichent sans exception ;
- le comportement a été essayé sur le CSV d'exemple, et sur le CSV réel quand il existe ;
- aucune fonctionnalité de la section 5 n'a régressé ;
- tu m'as indiqué clairement ce qui a changé, ce qui a été vérifié, et ce qui ne l'a pas été.

══════════ 9. FORMAT DE TES RÉPONSES ══════════

1. Ce que tu as compris de la tâche (2 à 3 lignes).
2. Plan en étapes courtes.
3. Attends ma validation.
Après validation : modifications, résultats des tests, résultat du lancement de l'application, limites restantes.

Commence par la MISSION 1. Ne code rien avant d'avoir lu les fichiers et exécuté les tests.

══════════ SUIVI DES MISSIONS ══════════

| Mission | Statut | Rapport |
|---|---|---|
| 1. Stabiliser | Terminée (rapport rendu, aucune correction) | [Mission 1](RAPPORT_MISSIONS.md#mission-1--stabiliser--rapport-aucune-correction-appliquée) |
| 2. Corrections validées | Terminée : B1, B2, G1–G5, G7, M1, M2 ; 45 tests OK | [Mission 2](RAPPORT_MISSIONS.md#mission-2--corrections-validées--rapport) |
| 3. Test de charge | Terminée : interactions 5–11 s → 0,2–0,3 s sur le CSV réel ; 46 tests OK | [Mission 3](RAPPORT_MISSIONS.md#mission-3--test-de-charge--rapport) |
| 4. Filtres + caractère générique + nettoyage du code | Terminée : filtres Retenir/Exclure (identifiant 16 s → 0,5 s), rôles FR/ISO, code mort retiré ; 49 tests OK | [Mission 4](RAPPORT_MISSIONS.md#mission-4--filtres-caractère-générique-et-nettoyage-du-code--rapport) |
| 5. Dashboard | Terminée : ordre unique (champ « Ligne » retiré), bouton « Modifier ce graphique », anciens JSON compatibles ; 51 tests OK | [Mission 5](RAPPORT_MISSIONS.md#mission-5--dashboard--ordre-largeur-modification--rapport) |
| 6. Règles de qualité | Terminée : avant/après décomposé (exclusions / résolutions / nouvelles) ; 54 tests OK | [Mission 6](RAPPORT_MISSIONS.md#mission-6--règles-de-qualité--rapport) |
| Nettoyage et restructuration | Terminée : code mort retiré, rangement par étape, Docker renommé | [Nettoyage](RAPPORT_MISSIONS.md#mission-de-nettoyage--étapes-0-et-1--état-de-départ-et-audit-lecture-seule) |
| Refonte : outil simple en 4 étapes | Terminée : Importer → Comprendre → Corriger → Visualiser ; mode expert gardé à côté ; 81 tests OK ; test navigateur et Docker réussis | [Refonte](RAPPORT_MISSIONS.md#refonte--outil-simple-en-4-étapes--réalisation-2026-10-22) |
| Mode expert léger | Terminé : boutons Mode simple / Mode expert ; règles simples, carte des règles, espaces en trop, filtre ; 92 tests OK ; navigateur et Docker réussis | [Mode expert léger](RAPPORT_MISSIONS.md#mode-expert-léger-2026-10-22) |
| Un seul parcours | Terminé : couleurs plus douces ; boutons de mode retirés ; règles facultatives dans le parcours ; type changé par l'étiquette ; Filtrage à l'étape 4 ; 92 tests OK ; navigateur réussi | [Un seul parcours](RAPPORT_MISSIONS.md#un-seul-parcours--règles-facultatives-et-filtrage-2026-10-22) |
| Design Sarcelle qualité | Terminé : couleurs sarcelle, cartes blanches, logo, couleurs de graphiques vérifiées ; 95 tests OK ; navigateur et Docker réussis | [Design](RAPPORT_MISSIONS.md#design--sarcelle-qualité--et-logo-2026-10-23) |
| Rapport complet | Terminé : rapport HTML avec graphiques, tableau des colonnes, pistes de lecture, filtre ; 2 défauts de validation corrigés ; 100 tests OK ; navigateur et Docker réussis | [Rapport complet](RAPPORT_MISSIONS.md#rapport-complet-avec-graphiques-et-pistes-de-lecture-2026-10-23) |
| Étape 5 Analyser | Terminée : comparer des groupes, délai, évolution, constats calculés, exports Power BI et Jupyter ; testée sur 4 domaines ; 115 tests OK ; navigateur réussi | [Analyser](RAPPORT_MISSIONS.md#étape-5--analyser--2026-10-23) |
| 7. Répétitions | Terminée (version légère) : volet « Pourquoi … se répète ? » sur les cartes Identifiant, lecture seule ; 95 tests OK ; navigateur réussi, aussi sur le fichier réel | [Mission 7](RAPPORT_MISSIONS.md#mission-7--répétitions-version-légère-2026-10-22) |

Tous les rapports sont regroupés dans un seul fichier : [RAPPORT_MISSIONS.md](RAPPORT_MISSIONS.md).

Note : la section 3 de ce cahier décrit un état plus ancien que le code (voir le rapport de la Mission 1, section 2).

Règle de périmètre (demandée le 2026-10-22) : travailler uniquement sur l'application `src/` ; ne pas toucher aux notebooks, à Power BI ni au `requirements.txt` racine. L'application doit rester générique (aucune colonne ni règle propre au jeu « incidents »).

Commandes : `python -m unittest discover -s src/tests` (depuis la racine) · `python -m streamlit run src/app.py`.
