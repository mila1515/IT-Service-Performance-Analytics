"""Le rapport qualité, organisé comme le parcours : étape 1 Importer → étape 5 Analyser.

Entrée : un dictionnaire `contenu` assemblé par l'écran :
`nom`, `taille`, `lecture` (séparateur, encodage, décimale en clair), `ids_texte`, `produit_le`, `lignes`,
`colonnes`, `empreinte`, `decisions`, `journal`, `resultat`, `notes`, `regles_verifiees`, `fiches`
(colonnes après corrections), `interpretations`, `graphiques` (descriptions de `controles`), `filtre`
(None, ou {texte, retenues, total}), `analyses` (résumés de l'étape Analyser).
`blocs` décrit le rapport une seule fois (titres, textes, listes, tableaux, graphiques) ; les versions
texte (Markdown), HTML et Word (`rapport_word.py`) ne font que le mettre en forme.
Le rapport décrit ce qui a été vérifié, décidé et vu ; il ne certifie pas l'exactitude des valeurs.
Dans le HTML, tout texte issu du fichier est échappé.
"""
from html import escape
from pathlib import Path

import vl_convert

from src.core.dessins import dessiner
from src.core.texte import nombre_lisible, pluriel
from src.etape2_comprendre.repetitions import part_lisible

LIMITES = ("Les vérifications portent sur la forme des données : codes de valeur manquante, textes dans des "
           "nombres, cases vides, lignes identiques et ordre des dates. Elles ne prouvent pas que les valeurs "
           "sont exactes, ni qu'elles répondent à la question métier.")
NOTE_PISTES = ("Pistes calculées à partir des chiffres seulement, sans règle métier : à vérifier avec ce que vous "
               "savez des données.")
NOTE_ECARTEES = ("Les lignes écartées ne sont pas effacées : elles sont dans le fichier des lignes écartées, avec leur "
                 "raison. Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé.")
RIEN_A_SIGNALER = "Rien de particulier à signaler."
NOTE_REGLES = "Une règle non respectée n'est pas forcément une erreur : elle signale un écart avec ce qui était attendu."
NOTE_IA = ("Suggestions générées par une IA à partir d'un résumé du fichier, sans ses lignes. Elles peuvent se tromper "
           "et n'ont pas été appliquées automatiquement : seules les décisions de l'étape 3 ont modifié les données.")
LOGO = Path(__file__).parents[1] / "assets" / "logo.svg"
POLICE = "Segoe UI, Inter, Arial, sans-serif"
LARGEUR_GRAPHIQUE = 640
ETAPES = ["Étape 1 · Importer", "Étape 2 · Comprendre", "Étape 3 · Corriger", "Étape 4 · Visualiser", "Étape 5 · Analyser"]


def _aucun_changement(journal):
    return not journal or journal[0].startswith("Aucun changement")


def taille_lisible(octets):
    """1 536 → « 1,5 Ko », 268 874 011 → « 256,4 Mo »."""
    if octets >= 1024 * 1024:
        return f"{nombre_lisible(round(octets / 1024 / 1024, 1))} Mo"
    return f"{nombre_lisible(round(octets / 1024, 1))} Ko"


def synthese(contenu):
    """Le rapport en quelques phrases, avant le détail."""
    resultat, fiches = contenu["resultat"], contenu["fiches"]
    cases = sum(f["total"] for f in fiches)
    remplies = sum(f["remplies"] for f in fiches)
    phrases = [
        f"{nombre_lisible(contenu['lignes'])} lignes et {nombre_lisible(contenu['colonnes'])} colonnes importées ; "
        f"{nombre_lisible(resultat['gardees'])} lignes gardées, {nombre_lisible(resultat['ecartees'])} écartées.",
        f"{part_lisible(remplies / cases) if cases else '100 %'} des cases sont remplies après corrections.",
        f"{pluriel(len(contenu['decisions']), 'point vérifié', 'points vérifiés')} ; "
        + ("aucune donnée modifiée." if _aucun_changement(contenu["journal"])
           else f"{pluriel(len(contenu['journal']), 'correction appliquée', 'corrections appliquées')}."),
    ]
    filtre = contenu["filtre"]
    phrases.append(f"Graphiques filtrés : {filtre['texte']} ({nombre_lisible(filtre['retenues'])} / "
                   f"{nombre_lisible(filtre['total'])} lignes)." if filtre
                   else "Graphiques calculés sur toutes les lignes gardées.")
    if contenu["interpretations"]:
        phrases.append(f"{pluriel(len(contenu['interpretations']), 'piste de lecture', 'pistes de lecture')} à l'étape 4.")
    n = len(contenu["analyses"])
    phrases.append(f"{pluriel(n, 'analyse', 'analyses')} à l'étape 5." if n else "Aucune analyse à l'étape 5.")
    return phrases


def resume_fiche(fiche):
    """Ce qu'il faut savoir d'une colonne, en une ligne."""
    role = fiche["role"]
    if role == "Identifiant":
        if not fiche["repetees"]:
            return "toutes les valeurs sont différentes"
        valeur, fois = fiche["exemple_repete"]
        return f"{pluriel(fiche['repetees'], 'valeur répétée', 'valeurs répétées')} (ex. « {valeur} » × {fois})"
    if role == "Catégorie":
        if not fiche["frequences"]:
            return "aucune valeur"
        valeur, effectif = fiche["frequences"][0]
        return f"la plus fréquente : « {valeur} » ({nombre_lisible(effectif)})"
    if role == "Mesure":
        if not fiche["nombres"]:
            return "aucun nombre"
        texte = (f"min {nombre_lisible(fiche['minimum'])} · médiane {nombre_lisible(fiche['mediane'])} · "
                 f"moyenne {nombre_lisible(fiche['moyenne'])} · max {nombre_lisible(fiche['maximum'])}")
        return texte + (f" · {pluriel(fiche['non_numeriques'], 'texte')}" if fiche["non_numeriques"] else "")
    if not fiche.get("lisibles"):
        return "aucune date lisible"
    texte = f"du {fiche['debut']:%d/%m/%Y} au {fiche['fin']:%d/%m/%Y}"
    return texte + (f" · {pluriel(fiche['illisibles'], 'date illisible', 'dates illisibles')}" if fiche["illisibles"] else "")


def lignes_resultat(resultat):
    lignes = [f"Lignes gardées : {nombre_lisible(resultat['gardees'])} sur {nombre_lisible(resultat['total'])}.",
              f"Lignes écartées : {nombre_lisible(resultat['ecartees'])}"
              + (" (" + ", ".join(f"{motif} : {nombre_lisible(n)}" for motif, n in resultat["motifs"]) + ")."
                 if resultat["motifs"] else "."),
              f"Cases vides : {nombre_lisible(resultat['vides_avant'])} avant, {nombre_lisible(resultat['vides_apres'])} après."]
    for m in resultat["moyennes"]:
        avant = nombre_lisible(m["avant"]) if m["avant"] is not None else "—"
        apres = nombre_lisible(m["apres"]) if m["apres"] is not None else "—"
        lignes.append(f"Moyenne de {m['colonne']} : {avant} avant ({nombre_lisible(m['n_avant'])} valeurs), "
                      f"{apres} après ({nombre_lisible(m['n_apres'])} valeurs).")
    return lignes


def lignes_regles(regles_verifiees):
    return [f"{regle} : " + (pluriel(len(n), "ligne ne respecte pas", "lignes ne respectent pas") if n
                             else "respectée par toutes les lignes") for regle, n in regles_verifiees.items()]


def _points_par_famille(decisions):
    familles = {}
    for decision in decisions:
        familles[decision["titre"]] = familles.get(decision["titre"], 0) + 1
    return [f"{titre} : {pluriel(n, 'point')}" for titre, n in familles.items()]


def _a_dessiner(element):
    return element.get("donnees") is not None and len(element["donnees"]) > 0


def _blocs_ia(ia):
    """Section présente seulement si l'Assistant IA a été utilisé."""
    if not ia:
        return []
    b = [("section", "Suggestions de l'IA"), ("discret", NOTE_IA)]
    if ia["resume"] or ia["a_regarder"]:
        b.append(("sous_titre", "Lecture du fichier"))
        if ia["resume"]:
            b.append(("texte", ia["resume"]))
        if ia["a_regarder"]:
            b.append(("puces", ia["a_regarder"]))
    if ia["suggestions"]:
        b += [("sous_titre", "Conseils de correction"),
              ("tableau", ["Problème", "Suggestion", "Raison", "Décision prise", "Suggestion"], ia["suggestions"])]
    if ia["pistes"]:
        b += [("sous_titre", "Pistes d'analyse"), ("puces", ia["pistes"])]
    return b


def blocs(contenu):
    """Le rapport, une fois pour toutes : liste de (genre, …) dans l'ordre de lecture.

    Genres : section, sous_titre, texte, discret, filtre, puces, decisions, tableau, graphique, retenir.
    """
    b = [("section", "En bref"), ("puces", synthese(contenu))]

    lecture = contenu.get("lecture") or {}
    importer = [f"Fichier : {contenu['nom']}" + (f" ({taille_lisible(contenu['taille'])})" if contenu.get("taille") else "") + ".",
                f"{nombre_lisible(contenu['lignes'])} lignes et {nombre_lisible(contenu['colonnes'])} colonnes."]
    if lecture:
        importer.append(f"Lecture : séparateur {lecture['separateur']}, encodage {lecture['encodage']}, "
                        f"décimale {lecture['decimale']}.")
    if contenu.get("ids_texte"):
        importer.append("Lues comme du texte pour garder les zéros au début : " + ", ".join(map(str, contenu["ids_texte"])) + ".")
    importer.append(f"Empreinte SHA-256 du fichier d'origine : {contenu['empreinte']}. Ce fichier n'a pas été modifié.")
    b += [("section", ETAPES[0]), ("puces", importer)]

    b.append(("section", ETAPES[1]))
    if contenu["decisions"]:
        b += [("texte", f"{pluriel(len(contenu['decisions']), 'point à vérifier repéré', 'points à vérifier repérés')} :"),
              ("puces", _points_par_famille(contenu["decisions"]))]
    else:
        b.append(("texte", "Aucun point à vérifier n'a été repéré."))
    if contenu["regles_verifiees"]:
        b += [("sous_titre", "Règles cochées"), ("puces", lignes_regles(contenu["regles_verifiees"])), ("discret", NOTE_REGLES)]

    b.append(("section", ETAPES[2]))
    if contenu["decisions"]:
        b += [("sous_titre", "Décisions"), ("decisions", [(d["texte"], d["choix"]) for d in contenu["decisions"]])]
    b += [("sous_titre", "Ce qui a été fait"), ("puces", contenu["journal"]),
          ("sous_titre", "Résultat"), ("puces", lignes_resultat(contenu["resultat"]))]
    if contenu["resultat"]["ecartees"]:
        b.append(("discret", NOTE_ECARTEES))
    b += [("sous_titre", "Les colonnes après corrections"),
          ("tableau", ["Colonne", "Type", "Remplie", "Valeurs différentes", "En résumé"],
           [[f["colonne"], f["libelle"], part_lisible(f["remplies"] / f["total"]) if f["total"] else "—",
             nombre_lisible(f["distinctes"]), resume_fiche(f)] for f in contenu["fiches"]])]

    b.append(("section", ETAPES[3]))
    filtre = contenu["filtre"]
    b.append(("filtre", f"Filtre appliqué aux graphiques : {filtre['texte']} ({nombre_lisible(filtre['retenues'])} / "
                        f"{nombre_lisible(filtre['total'])} lignes). Les données téléchargées ne sont pas filtrées.")
             if filtre else ("discret", "Graphiques de contrôle calculés sur toutes les lignes gardées."))
    for g in contenu["graphiques"]:
        b += [("sous_titre", g["titre"]), ("discret", g["sous_titre"])]
        if _a_dessiner(g):
            b.append(("graphique", g))
        b.append(("retenir", "À retenir : ", " ".join(g["a_retenir"])))
    if not contenu["graphiques"]:
        b.append(("texte", "Aucun graphique de contrôle possible avec les types de colonnes choisis."))
    if contenu["interpretations"]:
        b += [("sous_titre", "Pistes de lecture"), ("discret", NOTE_PISTES), ("puces", contenu["interpretations"])]

    b.append(("section", ETAPES[4]))
    if contenu["analyses"]:
        b.append(("discret", "Calculées sur les données corrigées, avec les colonnes choisies à l'étape Analyser."))
        for a in contenu["analyses"]:
            b += [("sous_titre", a["titre"]), ("discret", a["sous_titre"])]
            if _a_dessiner(a):
                b.append(("graphique", a))
            if a["tableau"] is not None and len(a["tableau"]):
                b.append(("tableau", list(a["tableau"].columns), [list(ligne) for ligne in a["tableau"].itertuples(index=False)]))
            b += [("retenir", "Ce que montrent les chiffres", ""), ("puces", a["a_retenir"] or [RIEN_A_SIGNALER]),
                  ("discret", a["prudence"])]
    else:
        b.append(("texte", "Aucune analyse : il faut une colonne de type Catégorie ou Date (étape Comprendre)."))

    b += _blocs_ia(contenu.get("ia"))
    if contenu["notes"].strip():
        b += [("section", "Notes"), ("texte", contenu["notes"].strip())]
    b += [("section", "Ce que ce rapport ne garantit pas"), ("texte", LIMITES)]
    return b


def _specification(graphique):
    """Le graphique de l'écran, avec une largeur fixe pour le rapport."""
    return (dessiner(graphique).properties(width=LARGEUR_GRAPHIQUE).configure(font=POLICE).configure_view(stroke=None)
            .configure_axis(labelFontSize=12, titleFontSize=12)).to_dict()


def svg_graphique(graphique):
    """Image SVG du graphique (rapport HTML)."""
    return vl_convert.vegalite_to_svg(_specification(graphique))


def png_graphique(graphique):
    """Image PNG du graphique, en double résolution (rapport Word)."""
    return vl_convert.vegalite_to_png(_specification(graphique), scale=2)


def _cellule_md(texte):
    return str(texte).replace("|", "\\|").replace("\n", " ")


def rapport_markdown(contenu):
    """Version texte : tout le rapport ; chaque graphique est décrit par son titre et « À retenir »."""
    texte = [f"# Rapport qualité — {contenu['nom']}", "", f"Produit le {contenu['produit_le']:%d/%m/%Y à %H:%M} (UTC)."]
    for genre, *valeurs in blocs(contenu):
        if genre == "section":
            texte += ["", f"## {valeurs[0]}"]
        elif genre == "sous_titre":
            texte += ["", f"### {valeurs[0]}"]
        elif genre in ("texte", "discret", "filtre"):
            texte += ["", valeurs[0]]
        elif genre == "puces":
            texte += [""] + [f"- {p}" for p in valeurs[0]]
        elif genre == "decisions":
            texte += [""] + [f"- {t} → **{c}**" for t, c in valeurs[0]]
        elif genre == "tableau":
            entetes, lignes = valeurs
            texte += ["", "| " + " | ".join(_cellule_md(c) for c in entetes) + " |", "|" + "---|" * len(entetes)]
            texte += ["| " + " | ".join(_cellule_md(v) for v in ligne) + " |" for ligne in lignes]
        elif genre == "retenir":
            texte += ["", f"**{valeurs[0].strip()}** {valeurs[1]}".rstrip()]
    return "\n".join(texte) + "\n"


STYLE = """
:root { --principale: #0B6F71; --fond: #F1F5F5; --carte: #FFFFFF; --encre: #1E2A38; --encre-2: #5B6673;
        --bordure: #D9DEE5; --doux: #E3F2F2; --alerte: #9A4B00; --alerte-fond: #FDF0E1; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--fond); color: var(--encre); font: 15px/1.55 "Segoe UI", Inter, Arial, sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 28px 20px 48px; display: flex; flex-direction: column; gap: 18px; }
header { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
header p { margin: 0; color: var(--encre-2); font-size: 13px; }
h1 { font-size: 26px; margin: 4px 0 0; }
h2 { font-size: 19px; margin: 0 0 10px; }
h3 { font-size: 16px; margin: 18px 0 4px; }
section { background: var(--carte); border: 1px solid var(--bordure); border-radius: 12px; padding: 18px 20px; }
section.bref { border-left: 4px solid var(--principale); }
section.etape h2 { color: var(--principale); }
section ul { margin: 6px 0; padding-left: 20px; }
p { margin: 6px 0; }
.discret { color: var(--encre-2); font-size: 13px; }
.tableau { overflow-x: auto; margin: 8px 0; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--bordure); vertical-align: top; }
th { background: var(--doux); color: var(--principale); font-weight: 600; }
svg { max-width: 100%; height: auto; display: block; margin: 8px 0; }
.filtre { background: var(--alerte-fond); color: var(--alerte); border-radius: 8px; padding: 8px 12px; }
.note { white-space: pre-line; }
@media print { body { background: #fff; } section { break-inside: avoid-page; } }
"""


def rapport_html(contenu):
    """Version à lire dans le navigateur, avec les graphiques dessinés ; imprimable en PDF."""
    e = escape
    parties, section = [], None

    def fermer():
        if section is not None:
            parties.append(section + "</section>")

    for genre, *valeurs in blocs(contenu):
        if genre == "section":
            fermer()
            classe = "bref" if valeurs[0] == "En bref" else ("etape" if valeurs[0] in ETAPES else "")
            section = f"<section class='{classe}'><h2>{e(valeurs[0])}</h2>"
            continue
        if genre == "sous_titre":
            morceau = f"<h3>{e(valeurs[0])}</h3>"
        elif genre == "texte":
            morceau = f"<p class='note'>{e(valeurs[0])}</p>"
        elif genre == "discret":
            morceau = f"<p class='discret'>{e(valeurs[0])}</p>"
        elif genre == "filtre":
            morceau = f"<p class='filtre'>{e(valeurs[0])}</p>"
        elif genre == "puces":
            morceau = "<ul>" + "".join(f"<li>{e(p)}</li>" for p in valeurs[0]) + "</ul>"
        elif genre == "decisions":
            morceau = "<ul>" + "".join(f"<li>{e(t)} → <strong>{e(c)}</strong></li>" for t, c in valeurs[0]) + "</ul>"
        elif genre == "tableau":
            entetes, lignes = valeurs
            morceau = ("<div class='tableau'><table><thead><tr>" + "".join(f"<th>{e(str(c))}</th>" for c in entetes)
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(v))}</td>" for v in ligne) + "</tr>"
                                                         for ligne in lignes) + "</tbody></table></div>")
        elif genre == "graphique":
            morceau = svg_graphique(valeurs[0])
        else:  # retenir
            morceau = f"<p><strong>{e(valeurs[0])}</strong>{e(valeurs[1])}</p>"
        section += morceau
    fermer()
    entete = (f"<header>{LOGO.read_text(encoding='utf-8')}<p>Produit le {contenu['produit_le']:%d/%m/%Y à %H:%M} (UTC)</p></header>"
              f"<h1>Rapport qualité — {e(contenu['nom'])}</h1>")
    return ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Rapport qualité — {e(contenu['nom'])}</title><style>{STYLE}</style></head>"
            f"<body><main>{entete}{''.join(parties)}</main></body></html>")
