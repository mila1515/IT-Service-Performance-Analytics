"""Test du parcours dans un vrai navigateur (Chromium, Playwright), sur un serveur Streamlit lancé à part.

Lancer depuis la racine du dépôt :
    python -m pip install playwright && python -m playwright install chromium
    python -m streamlit run src/app.py --server.headless=true --server.port=8650
    python src/tests/navigateur/parcours_navigateur.py http://127.0.0.1:8650 [chemin/vers/un_autre.csv]

Affiche « réussi / échec » pour chaque étape, avec le temps ; capture d'écran en cas d'échec.
Code de sortie 1 si une étape échoue. Non lancé par `unittest` (il faut un serveur et Chromium).
"""
import io
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

RACINE = Path(__file__).resolve().parents[3]
EXEMPLE = RACINE / "src" / "tests" / "fixtures" / "exemple.csv"
CAPTURES = Path(tempfile.gettempdir()) / "parcours_navigateur"


class Parcours:
    def __init__(self, page):
        self.page = page
        self.resultats = []

    def fin_execution(self, timeout=180000):
        """Attend que Streamlit ait fini de réexécuter le script."""
        self.page.wait_for_timeout(300)
        self.page.wait_for_function(
            "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')?.innerText?.includes('Running')", timeout=timeout)

    def voir(self, texte, timeout=180000):
        self.page.get_by_text(texte).first.wait_for(timeout=timeout)

    def bouton(self, nom):
        return self.page.get_by_role("button", name=nom)

    def choisir(self, libelle_option):
        """Clique une option d'un contrôle segmenté (exposée comme bouton radio, pour l'accessibilité)."""
        self.page.get_by_role("radio", name=libelle_option, exact=True).first.click()
        self.fin_execution()

    def etape(self, nom, action):
        debut = time.perf_counter()
        try:
            details = action()
            self.fin_execution()
            self.resultats.append((nom, "réussi", time.perf_counter() - debut, details or ""))
        except Exception as exc:  # noqa: BLE001 — chaque échec est rapporté, le parcours continue
            CAPTURES.mkdir(exist_ok=True)
            capture = CAPTURES / f"echec_{len(self.resultats) + 1}.png"
            self.page.screenshot(path=str(capture), full_page=True)
            self.resultats.append((nom, "échec", time.perf_counter() - debut, f"{type(exc).__name__}: {str(exc)[:200]} — {capture}"))

    def telecharger(self, nom_bouton):
        with self.page.expect_download(timeout=120000) as attente:
            self.bouton(nom_bouton).click()
        chemin = attente.value.path()
        return attente.value.suggested_filename, Path(chemin).read_bytes()


def parcours_exemple(p, url):
    page = p.new_page(viewport={"width": 1400, "height": 1200}, accept_downloads=True)
    t = Parcours(page)
    page.goto(url, wait_until="networkidle")
    t.voir("Importer votre fichier")

    def importer():
        page.locator("input[type=file]").set_input_files(str(EXEMPLE))
        t.voir("Fichier lu correctement")
        t.voir("7 lignes et 4 colonnes")
        assert page.get_by_text("exemple.csv").count() > 0
    t.etape("1. Importer : nom, lignes, colonnes, aperçu", importer)

    def mauvais_separateur():
        page.get_by_text("Le tableau ne ressemble pas à votre fichier ?").click()
        t.choisir("Point-virgule ( ; )")
        t.voir("Le tableau semble mal découpé")
        t.choisir("Virgule ( , )")
        t.voir("Fichier lu correctement")
    t.etape("2. Mauvais séparateur : message compréhensible", mauvais_separateur)

    def comprendre():
        t.bouton("Étape suivante : comprendre mes données").click()
        t.voir("Vos 4 colonnes")
        t.fin_execution()
        t.voir("« 004 » apparaît 2 fois")
        t.voir("Bon réflexe")
    t.etape("3. Explorer : colonnes, manquants, doublons", comprendre)

    def corriger():
        t.bouton("Étape suivante : corriger 4 points").click()
        t.voir("Résultat de vos choix")
        t.fin_execution()
        t.choisir("C'est une valeur manquante")
        t.voir("categorie : 2 cases vides")
        t.choisir("Garder une seule ligne")
        t.voir("parce que sa ligne est écartée n'a pas été réparé")
    t.etape("4. Nettoyer : « ? » reconnu comme vide, traitement choisi", corriger)

    def comparer():
        texte = page.locator('[data-testid="stAlertContentWarning"]').first.inner_text()
        assert "copie identique d'une autre ligne" in texte, texte
        t.voir("6 / 7")
    t.etape("5. Avant / après : exclusion distinguée de la correction", comparer)

    def visualiser():
        t.bouton("Valider et voir les graphiques").click()
        t.voir("Vérifier vos données en graphiques")
        t.fin_execution()
        assert page.get_by_text("À retenir").count() >= 3
        t.choisir("Comment se répartit une colonne")
        t.bouton("Ajouter ce graphique").click()
        t.fin_execution()
        assert t.bouton("Retirer").count() == 1
    t.etape("6. Visualiser : graphiques de contrôle, ajout d'un graphique", visualiser)

    def telechargements():
        details = []
        nom, contenu = t.telecharger("Données corrigées (CSV)")
        assert "001" in contenu.decode("utf-8-sig"), "zéros initiaux perdus"
        details.append(f"{nom} ({len(contenu)} o)")
        nom, contenu = t.telecharger("Lignes écartées (CSV)")
        assert contenu.decode("utf-8-sig").startswith("Ligne d'origine,Raison"), contenu[:80]
        details.append(f"{nom} ({len(contenu)} o)")
        nom, contenu = t.telecharger("Rapport qualité")
        assert "Écarter" in contenu.decode("utf-8") or "écartées" in contenu.decode("utf-8")
        details.append(f"{nom} ({len(contenu)} o)")
        nom, contenu = t.telecharger("Tout le projet (ZIP)")
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            assert archive.read("fichier_origine/exemple.csv") == EXEMPLE.read_bytes(), "fichier d'origine modifié"
            json.loads(archive.read("journal.json"))
        details.append(f"{nom} ({len(contenu)} o, fichier d'origine identique)")
        return " · ".join(details)
    t.etape("7. Synthèse : chaque téléchargement produit un fichier lisible", telechargements)

    def changement_options():
        page.get_by_role("radio", name="1 · Importer").click()
        t.fin_execution()
        page.get_by_text("Le tableau ne ressemble pas à votre fichier ?").click()
        t.choisir("Virgule ( 10,5 )")
        t.voir("vos choix ont été effacés")
    t.etape("9. Changer une option de lecture après du travail : avertissement", changement_options)
    page.close()
    return t.resultats


def parcours_expert(p, url):
    """Mode expert léger : règle simple, carte des règles non respectées, filtre avant les graphiques."""
    page = p.new_page(viewport={"width": 1400, "height": 1200}, accept_downloads=True)
    t = Parcours(page)
    page.goto(url, wait_until="networkidle")
    t.voir("Importer votre fichier")
    page.locator("input[type=file]").set_input_files(str(EXEMPLE))
    t.voir("Fichier lu correctement")
    t.fin_execution()

    def regle():
        t.choisir("Mode expert")
        t.bouton("Étape suivante : comprendre mes données").click()
        t.voir("Mode expert : règles simples")
        t.fin_execution()
        page.locator('[data-testid="stCheckbox"]').filter(has_text="Valeurs uniques").click()
        t.fin_execution()
        t.voir("2 lignes ne respectent pas (lignes 4, 6)")
    t.etape("E1. Mode expert : règle « valeurs uniques » cochée et vérifiée", regle)

    def carte_regles():
        t.bouton("Étape suivante : corriger").click()
        t.voir("Règles non respectées")
        t.fin_execution()
        t.voir("2 lignes signalées, gardées")
        page.get_by_role("radio", name="Écarter ces lignes").last.click()
        t.fin_execution()
        t.voir("5 / 7")
    t.etape("E2. Mode expert : règle non respectée → lignes écartées", carte_regles)

    def filtre():
        t.bouton("Valider et voir les graphiques").click()
        t.voir("Filtrer avant de regarder")
        t.fin_execution()
        t.choisir("Exclure")
        page.get_by_role("button", name="A", exact=True).click()
        t.fin_execution()
        t.voir("lignes retenues")
        texte = page.get_by_text("lignes retenues").first.inner_text()
        assert texte.startswith("4 / 5"), texte
        nom, contenu = t.telecharger("Données corrigées (CSV)")
        assert contenu.decode("utf-8-sig").count("\n") == 6, "le filtre ne doit pas changer les données téléchargées"
        nom, contenu = t.telecharger("Rapport qualité")
        assert "Règles vérifiées (mode expert)" in contenu.decode("utf-8")
        return texte
    t.etape("E3. Mode expert : filtre sur les graphiques, téléchargements inchangés", filtre)
    page.close()
    return t.resultats


def parcours_reel(p, url, csv):
    page = p.new_page(viewport={"width": 1400, "height": 1200}, accept_downloads=True)
    t = Parcours(page)
    page.goto(url, wait_until="networkidle")
    t.voir("Importer votre fichier")
    t.etape(f"R1. Import ({csv.name})", lambda: (page.locator("input[type=file]").set_input_files(str(csv)), t.voir("Fichier lu correctement")))
    t.etape("R3. Explorer", lambda: (t.bouton("Étape suivante : comprendre mes données").click(), t.voir("À vérifier avant d'analyser")))
    t.etape("R. Réexécution à l'étape Explorer", lambda: page.keyboard.press("r"))
    t.etape("R4. Arrivée Corriger", lambda: (t.bouton("Étape suivante : corriger").click(), t.voir("Résultat de vos choix")))
    t.etape("R4. Choix « ? » = valeur manquante", lambda: t.choisir("C'est une valeur manquante"))
    t.etape("R6. Visualiser", lambda: (t.bouton("Valider et voir les graphiques").click(), t.voir("À retenir")))
    t.etape("R. Réexécution à l'étape Visualiser", lambda: page.keyboard.press("r"))
    page.close()
    return t.resultats


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8650"
    reel = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    with sync_playwright() as playwright:
        navigateur = playwright.chromium.launch(headless=True)
        resultats = parcours_exemple(navigateur, url)
        resultats += parcours_expert(navigateur, url)
        if reel:
            resultats += parcours_reel(navigateur, url, reel)
        navigateur.close()
    for nom, statut, duree, details in resultats:
        print(f"{'OK ' if statut == 'réussi' else 'KO '} {nom:62s} {duree:5.1f}s  {details}")
    sys.exit(0 if all(statut == "réussi" for _, statut, _, _ in resultats) else 1)


if __name__ == "__main__":
    main()
