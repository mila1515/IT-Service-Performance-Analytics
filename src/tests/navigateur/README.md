# Test dans un vrai navigateur

Parcours complet dans Chromium : import, mauvais séparateur, exploration, corrections, distinction
écarter/corriger, graphiques, clic sur chaque téléchargement (fichiers relus), avertissement en cas
de changement d'option, puis le mode expert (règle cochée, carte des règles, filtre). Non lancé par `unittest` (il faut un serveur et Chromium).

```powershell
python -m pip install playwright ; python -m playwright install chromium
python -m streamlit run src/app.py --server.headless=true --server.port=8650
python src/tests/navigateur/parcours_navigateur.py http://127.0.0.1:8650 data/raw/un_fichier.csv
```

Le second argument (facultatif) ajoute un parcours chronométré sur un gros fichier.
Captures d'écran des échecs : dossier temporaire `parcours_navigateur`.
