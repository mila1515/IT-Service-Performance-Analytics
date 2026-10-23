"""Étape 4 (Exporter) : rapport qualité en deux versions, Markdown (texte) et HTML (avec les graphiques).

Entrée : un dictionnaire `contenu` assemblé par l'écran :
`nom`, `produit_le`, `lignes`, `colonnes`, `empreinte`, `decisions`, `journal`, `resultat`, `notes`,
`regles_verifiees`, `fiches` (colonnes après corrections), `interpretations`, `graphiques`
(descriptions de `controles`), `filtre` (None, ou {texte, retenues, total}).
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
NOTE_REGLES = "Une règle non respectée n'est pas forcément une erreur : elle signale un écart avec ce qui était attendu."
LOGO = Path(__file__).parents[1] / "assets" / "logo.svg"
POLICE = "Segoe UI, Inter, Arial, sans-serif"
LARGEUR_GRAPHIQUE = 640


def _aucun_changement(journal):
    return not journal or journal[0].startswith("Aucun changement")


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
        phrases.append(f"{pluriel(len(contenu['interpretations']), 'piste de lecture', 'pistes de lecture')} plus bas.")
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


def _resultat(resultat):
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


def _regles(regles_verifiees):
    return [f"{regle} : " + (pluriel(len(n), "ligne ne respecte pas", "lignes ne respectent pas") if n
                             else "respectée par toutes les lignes") for regle, n in regles_verifiees.items()]


def _cellule_md(texte):
    return str(texte).replace("|", "\\|").replace("\n", " ")


def rapport_markdown(contenu):
    """Version texte : tout le contenu du rapport, les graphiques décrits par leur titre et « À retenir »."""
    resultat = contenu["resultat"]
    texte = [f"# Rapport qualité — {contenu['nom']}", "",
             f"Produit le {contenu['produit_le']:%d/%m/%Y à %H:%M} (UTC).", "",
             "## En bref", ""] + [f"- {p}" for p in synthese(contenu)]
    texte += ["", "## Le fichier", "",
              f"- {nombre_lisible(contenu['lignes'])} lignes, {nombre_lisible(contenu['colonnes'])} colonnes.",
              f"- Empreinte SHA-256 du fichier d'origine : `{contenu['empreinte']}`. Ce fichier n'a pas été modifié.",
              "", "## Les colonnes (après corrections)", "",
              "| Colonne | Type | Remplie | Valeurs différentes | En résumé |", "|---|---|---|---|---|"]
    texte += [f"| {_cellule_md(f['colonne'])} | {f['libelle']} | {part_lisible(f['remplies'] / f['total']) if f['total'] else '—'} "
              f"| {nombre_lisible(f['distinctes'])} | {_cellule_md(resume_fiche(f))} |" for f in contenu["fiches"]]
    texte += ["", "## Points vérifiés et décisions", ""]
    texte += [f"- {d['texte']} → **{d['choix']}**" for d in contenu["decisions"]] or ["- Aucun point à vérifier n'a été repéré."]
    texte += ["", "## Ce qui a été fait", ""] + [f"- {phrase}" for phrase in contenu["journal"]]
    texte += ["", "## Résultat", ""] + [f"- {ligne}" for ligne in _resultat(resultat)]
    if resultat["ecartees"]:
        texte += ["", "Les lignes écartées ne sont pas effacées : elles sont dans le fichier des lignes écartées, avec leur raison. "
                      "Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé."]
    if contenu["regles_verifiees"]:
        texte += ["", "## Règles vérifiées", ""] + [f"- {r}" for r in _regles(contenu["regles_verifiees"])] + ["", NOTE_REGLES]
    if contenu["interpretations"]:
        texte += ["", "## Pistes de lecture", "", NOTE_PISTES, ""] + [f"- {p}" for p in contenu["interpretations"]]
    texte += ["", "## Graphiques de contrôle", "",
              (f"Filtre appliqué aux graphiques : {contenu['filtre']['texte']}. Les données téléchargées ne sont pas filtrées."
               if contenu["filtre"] else "Calculés sur toutes les lignes gardées.")
              + " Les graphiques sont dessinés dans le rapport HTML."]
    for g in contenu["graphiques"]:
        texte += ["", f"### {g['titre']}", "", g["sous_titre"], "", "**À retenir :** " + " ".join(g["a_retenir"])]
    if contenu["notes"].strip():
        texte += ["", "## Notes", "", contenu["notes"].strip()]
    texte += ["", "## Ce que ce rapport ne garantit pas", "", LIMITES]
    return "\n".join(texte) + "\n"


def svg_graphique(graphique):
    """Le graphique de l'écran, en image SVG (même dessin, largeur fixe pour le rapport)."""
    graphique_altair = (dessiner(graphique).properties(width=LARGEUR_GRAPHIQUE)
                        .configure(font=POLICE).configure_view(stroke=None)
                        .configure_axis(labelFontSize=12, titleFontSize=12))
    return vl_convert.vegalite_to_svg(graphique_altair.to_dict())


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
h3 { font-size: 16px; margin: 0; }
section { background: var(--carte); border: 1px solid var(--bordure); border-radius: 12px; padding: 18px 20px; }
.bref { border-left: 4px solid var(--principale); }
.bref ul, section ul { margin: 0; padding-left: 20px; }
.discret { color: var(--encre-2); font-size: 13px; margin: 6px 0 0; }
.tableau { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--bordure); vertical-align: top; }
th { background: var(--doux); color: var(--principale); font-weight: 600; }
td.nombre { font-variant-numeric: tabular-nums; white-space: nowrap; }
.type { display: inline-block; font-size: 12px; padding: 1px 8px; border-radius: 6px; background: var(--doux); color: var(--principale); }
.pistes li { margin-bottom: 6px; }
.graphiques { display: flex; flex-direction: column; gap: 14px; }
.graphique { border: 1px solid var(--bordure); border-radius: 10px; padding: 14px 16px; }
.graphique svg { max-width: 100%; height: auto; display: block; margin: 8px 0; }
.retenir { margin: 0; }
.filtre { background: var(--alerte-fond); color: var(--alerte); border-radius: 8px; padding: 8px 12px; margin: 0 0 12px; }
code { font-size: 12px; word-break: break-all; }
@media print { body { background: #fff; } section { break-inside: avoid; } }
"""


def _liste(elements):
    return "<ul>" + "".join(f"<li>{escape(e)}</li>" for e in elements) + "</ul>"


def rapport_html(contenu):
    """Version à lire dans le navigateur, avec les graphiques dessinés ; imprimable en PDF."""
    e = escape
    resultat, filtre = contenu["resultat"], contenu["filtre"]
    lignes_colonnes = "".join(
        f"<tr><td>{e(f['colonne'])}</td><td><span class='type'>{e(f['libelle'])}</span></td>"
        f"<td class='nombre'>{part_lisible(f['remplies'] / f['total']) if f['total'] else '—'}</td>"
        f"<td class='nombre'>{nombre_lisible(f['distinctes'])}</td><td>{e(resume_fiche(f))}</td></tr>"
        for f in contenu["fiches"])
    decisions = "".join(f"<li>{e(d['texte'])} → <strong>{e(d['choix'])}</strong></li>" for d in contenu["decisions"])
    graphiques = "".join(
        f"<div class='graphique'><h3>{e(g['titre'])}</h3><p class='discret'>{e(g['sous_titre'])}</p>"
        f"{svg_graphique(g)}<p class='retenir'><strong>À retenir :</strong> {e(' '.join(g['a_retenir']))}</p></div>"
        for g in contenu["graphiques"]) or "<p>Aucun graphique de contrôle possible avec les types de colonnes choisis.</p>"
    parties = [
        f"<header>{LOGO.read_text(encoding='utf-8')}<p>Produit le {contenu['produit_le']:%d/%m/%Y à %H:%M} (UTC)</p></header>",
        f"<h1>Rapport qualité — {e(contenu['nom'])}</h1>",
        f"<section class='bref'><h2>En bref</h2>{_liste(synthese(contenu))}</section>",
        f"<section><h2>Le fichier</h2><ul><li>{nombre_lisible(contenu['lignes'])} lignes, "
        f"{nombre_lisible(contenu['colonnes'])} colonnes.</li><li>Empreinte SHA-256 du fichier d'origine : "
        f"<code>{e(contenu['empreinte'])}</code>. Ce fichier n'a pas été modifié.</li></ul></section>",
        "<section><h2>Les colonnes (après corrections)</h2><div class='tableau'><table><thead><tr><th>Colonne</th>"
        "<th>Type</th><th>Remplie</th><th>Valeurs différentes</th><th>En résumé</th></tr></thead>"
        f"<tbody>{lignes_colonnes}</tbody></table></div></section>",
        f"<section><h2>Points vérifiés et décisions</h2><ul>{decisions or '<li>Aucun point à vérifier n’a été repéré.</li>'}</ul></section>",
        f"<section><h2>Ce qui a été fait</h2>{_liste(contenu['journal'])}<h2 style='margin-top:14px'>Résultat</h2>"
        f"{_liste(_resultat(resultat))}"
        + ("<p class='discret'>Les lignes écartées ne sont pas effacées : elles sont dans le fichier des lignes écartées, "
           "avec leur raison. Un problème qui disparaît parce que sa ligne est écartée n'a pas été réparé.</p>"
           if resultat["ecartees"] else "") + "</section>",
    ]
    if contenu["regles_verifiees"]:
        parties.append(f"<section><h2>Règles vérifiées</h2>{_liste(_regles(contenu['regles_verifiees']))}"
                       f"<p class='discret'>{NOTE_REGLES}</p></section>")
    if contenu["interpretations"]:
        parties.append(f"<section class='pistes'><h2>Pistes de lecture</h2><p class='discret'>{NOTE_PISTES}</p>"
                       f"{_liste(contenu['interpretations'])}</section>")
    parties.append("<section><h2>Graphiques de contrôle</h2>"
                   + (f"<p class='filtre'>Filtre appliqué aux graphiques : {e(filtre['texte'])} "
                      f"({nombre_lisible(filtre['retenues'])} / {nombre_lisible(filtre['total'])} lignes). "
                      "Les données téléchargées ne sont pas filtrées.</p>" if filtre
                      else "<p class='discret'>Calculés sur toutes les lignes gardées.</p>")
                   + f"<div class='graphiques'>{graphiques}</div></section>")
    if contenu["notes"].strip():
        parties.append(f"<section><h2>Notes</h2><p style='white-space:pre-line'>{e(contenu['notes'].strip())}</p></section>")
    parties.append(f"<section><h2>Ce que ce rapport ne garantit pas</h2><p>{LIMITES}</p></section>")
    return ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Rapport qualité — {e(contenu['nom'])}</title><style>{STYLE}</style></head>"
            f"<body><main>{''.join(parties)}</main></body></html>")
