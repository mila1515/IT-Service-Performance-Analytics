"""Étape 4 (Visualiser et exporter) : contrôler en graphiques que les données corrigées sont plausibles, puis les remettre.

Entrées en session : `validation` (résultat validé à l'étape 3), `graphiques_ajoutes`, `notes`.
Sorties : téléchargements (données corrigées, lignes écartées, rapport complet HTML, rapport texte, archive).
Les graphiques servent au contrôle avant l'analyse métier, pas à en tirer des conclusions.
"""
from datetime import datetime, timezone
from functools import partial

import streamlit as st

from src.core.dessins import dessiner
from src.config import LIBELLE_MANQUANT
from src.core.session import aller, cached
from src.etape2_comprendre.colonnes import resume_colonnes
from src.etape2_comprendre.ecran import points_courants
from src.etape2_comprendre.repetitions import variations
from src.etape3_corriger.correction import decisions, phrases_journal
from src.etape4_visualiser.controles import comparaison, distribution, evolution, graphiques_controle, repartition
from src.etape4_visualiser.graphiques import apply_filters
from src.etape4_visualiser.export import archive_projet, csv_bytes, rejets_lisibles
from src.etape4_visualiser.interpretations import interpretations
from src.etape4_visualiser.preparation import prepare
from src.etape4_visualiser.rapport import rapport_html, rapport_markdown

QUESTIONS = {
    "repartition": ("Comment se répartit une colonne", "Ex. : combien de lignes par catégorie"),
    "temps": ("Comment ça évolue dans le temps", "Ex. : nombre de lignes par mois"),
    "comparer": ("Comparer des groupes", "Ex. : moyenne d'un nombre par catégorie"),
}


def _roles(validation):
    return {d["Colonne"]: d["Rôle"] for d in validation["plan"]["dictionary"]}


def _graphique_ajoute(data, roles, spec, ignorees):
    colonne = spec["colonne"]
    if spec["question"] == "temps":
        return evolution(data, colonne)
    if spec["question"] == "comparer":
        return comparaison(data, spec["groupe"], colonne, ignorees.get(colonne, 0))
    return distribution(data, colonne, ignorees.get(colonne, 0)) if roles[colonne] == "Mesure" else repartition(data, colonne)


def _carte(graphique, numero, retirer=None):
    with st.container(border=True, height="stretch", key=f"carte_graphique_{numero}"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{graphique['titre']}**")
            if retirer is not None:
                st.button("Retirer", key=f"w_ajout_retirer_{retirer}", type="tertiary", icon=":material/close:",
                          on_click=_retirer, args=(retirer,))
        st.caption(graphique["sous_titre"])
        st.altair_chart(dessiner(graphique), alt=f"{graphique['titre']}. {' '.join(graphique['a_retenir'])}")
        st.markdown("**À retenir :** " + " ".join(graphique["a_retenir"]))


def _retirer(index):
    etat = st.session_state
    etat.graphiques_ajoutes = [g for i, g in enumerate(etat.graphiques_ajoutes) if i != index]


def _ajouter(spec):
    st.session_state.graphiques_ajoutes = [*st.session_state.graphiques_ajoutes, spec]


def _section_ajout(roles):
    with st.container(border=True, key="carte_ajout"):
        st.subheader("Ajouter un graphique", anchor=False)
        question = st.segmented_control("Que voulez-vous voir ?", list(QUESTIONS), key="w_ajout_question",
                                        format_func=lambda q: QUESTIONS[q][0])
        if question is None:
            st.caption(" · ".join(f"{titre} — {exemple}" for titre, exemple in QUESTIONS.values()))
            return
        par_role = {role: [c for c, r in roles.items() if r == role] for role in ("Catégorie", "Mesure", "Date", "Identifiant")}
        spec = {"question": question}
        with st.container(horizontal=True, vertical_alignment="bottom"):
            if question == "temps":
                choix = par_role["Date"]
                spec["colonne"] = st.selectbox("Colonne de date", choix, key="w_ajout_date") if choix else None
            elif question == "comparer":
                spec["groupe"] = st.selectbox("Groupes à comparer", par_role["Catégorie"], key="w_ajout_groupe") if par_role["Catégorie"] else None
                spec["colonne"] = st.selectbox("Nombre à comparer", par_role["Mesure"], key="w_ajout_mesure") if par_role["Mesure"] else None
            else:
                choix = par_role["Catégorie"] + par_role["Mesure"]
                spec["colonne"] = st.selectbox("Colonne", choix, key="w_ajout_colonne") if choix else None
            manque = spec.get("colonne") is None or (question == "comparer" and spec.get("groupe") is None)
            st.button("Ajouter ce graphique", type="primary", icon=":material/add_chart:", disabled=manque,
                      on_click=_ajouter, args=(spec,))
        if manque:
            st.caption("Aucune colonne compatible : vérifiez les rôles à l'étape Comprendre.")


def _dayfirst(validation):
    return {col: valeur == "jour" for col, valeur in validation["choix"].get("dates", {}).items()}


def _graphiques_sans_filtre(validation, ajoutes):
    roles = _roles(validation)
    data, ignorees = prepare(validation["cleaned"], roles, _dayfirst(validation))
    return graphiques_controle(data, roles, ignorees) + [
        g for spec in ajoutes if (g := _graphique_ajoute(data, roles, spec, ignorees)) is not None]


def _contenu_rapport(base, validation, graphiques, filtre, ajoutes):
    """Tout ce que montre le rapport ; calculé au clic sur un téléchargement (parcourt tout le fichier)."""
    cleaned, dictionnaire = validation["cleaned"], validation["plan"]["dictionary"]
    if graphiques is None:
        graphiques = _graphiques_sans_filtre(validation, ajoutes)
    fiches = resume_colonnes(cleaned, dictionnaire, _dayfirst(validation))
    repetitions = {f["colonne"]: variations(cleaned, f["colonne"]) for f in fiches
                   if f["role"] == "Identifiant" and f["repetees"]}
    return {**base, "produit_le": datetime.now(timezone.utc), "fiches": fiches, "graphiques": graphiques,
            "filtre": filtre, "interpretations": interpretations(fiches, repetitions, validation["resultat"])}


def contenu_rapport(validation, graphiques=None, filtre=None):
    """Contenu du rapport : figé à l'affichage (décisions, notes, analyses de l'étape 5), calculé au clic.

    Retourne une fonction sans argument. Sans `graphiques` (rapport demandé hors de l'étape 4), les
    graphiques de contrôle sont recalculés sans filtre.
    """
    etat = st.session_state
    source = etat.source
    base = {"nom": source["nom"], "lignes": etat.raw.shape[0], "colonnes": etat.raw.shape[1],
            "empreinte": source["empreinte"], "decisions": decisions(points_courants(validation["choix"]), validation["choix"]),
            "journal": phrases_journal(validation["log"], validation.get("regles_signalees", ())),
            "resultat": validation["resultat"], "notes": etat.get("notes", ""),
            "regles_verifiees": validation.get("regles_verifiees") or {}, "analyses": list(etat.get("analyses") or [])}
    return partial(_contenu_rapport, base, validation, graphiques, filtre, list(etat.graphiques_ajoutes))


def _section_export(validation, graphiques, filtre):
    etat = st.session_state
    with st.container(border=True, key="carte_export"):
        st.subheader("Télécharger votre travail", anchor=False)
        st.caption("Rien n'est enregistré en ligne : téléchargez avant de fermer la page. Votre fichier d'origine n'a pas été modifié.")
        notes = st.text_area("Ce que je retiens (facultatif)", value=etat.get("notes", ""), key="w_notes",
                             placeholder="Par exemple : la catégorie A est la plus fréquente ; vérifier avec l'équipe "
                                         "si les lignes identiques sont de vraies lignes.")
        etat.notes = notes
        source = etat.source
        contenu = contenu_rapport(validation, graphiques, filtre)
        base = source["nom"].rsplit(".", 1)[0]
        with st.container(horizontal=True):
            # Fichiers générés au clic seulement : aucun coût à chaque interaction.
            st.download_button("Données corrigées (CSV)", partial(csv_bytes, validation["cleaned"]),
                               f"{base}_corrige.csv", "text/csv", icon=":material/table:", on_click="ignore")
            st.download_button("Lignes écartées (CSV)", lambda: csv_bytes(rejets_lisibles(validation["rejects"])),
                               f"{base}_lignes_ecartees.csv", "text/csv", icon=":material/playlist_remove:", on_click="ignore")
            st.download_button("Rapport complet (HTML)", lambda: rapport_html(contenu()).encode("utf-8"),
                               f"{base}_rapport_qualite.html", "text/html", icon=":material/insert_chart:", on_click="ignore",
                               help="Le rapport avec les graphiques et les pistes de lecture, à ouvrir dans le navigateur.")
            st.download_button("Rapport qualité (texte)", lambda: rapport_markdown(contenu()).encode("utf-8"),
                               f"{base}_rapport_qualite.md", "text/markdown", icon=":material/description:", on_click="ignore")
            st.download_button("Tout le projet (ZIP)",
                               lambda: _archive(source, validation, contenu()),
                               f"{base}_projet_{datetime.now(timezone.utc):%Y%m%d}.zip", "application/zip",
                               type="primary", icon=":material/folder_zip:", on_click="ignore")


def _filtre_categorie(data, colonnes):
    colonne = st.selectbox("Colonne à filtrer", colonnes, key="w_filtre_colonne")
    mode = st.segmented_control("Mode du filtre", ["garder", "exclure"], default="garder", required=True,
                                format_func={"garder": "Garder", "exclure": "Exclure"}.get, key="w_filtre_mode")
    valeurs = data[colonne].astype("string").value_counts().index.tolist()
    options = valeurs + ([LIBELLE_MANQUANT] if data[colonne].isna().any() else [])
    # Sélection de départ qui garde toutes les lignes, quel que soit le mode.
    defaut = options if mode == "garder" else []
    cle = f"w_filtre_valeurs_{colonne}_{mode}"
    if len(options) <= 30:
        choisies = st.pills("Valeurs", options, selection_mode="multi", default=defaut, key=cle)
    else:
        choisies = st.multiselect("Valeurs", options, default=defaut, key=cle)
    manquantes = LIBELLE_MANQUANT in choisies
    spec = {"column": colonne, "type": "Catégorie", "values": [v for v in choisies if v != LIBELLE_MANQUANT],
            "missing": manquantes if mode == "garder" else not manquantes, "exclude": mode == "exclure"}
    resume = f"{colonne} : {'garder' if mode == 'garder' else 'exclure'} {', '.join(choisies) or 'aucune valeur'}"
    return spec, resume


def _filtre_dates(data, colonne):
    dates = data[colonne].dropna()
    debut, fin = dates.min().date(), dates.max().date()
    periode = st.date_input(f"Période ({colonne})", value=(debut, fin), min_value=debut, max_value=fin,
                            format="DD/MM/YYYY", key=f"w_filtre_dates_{colonne}")
    if len(periode) != 2 or tuple(periode) == (debut, fin):
        return None, None
    spec = {"column": colonne, "type": "Date", "low": periode[0].isoformat(), "high": periode[1].isoformat(), "missing": False}
    return spec, f"{colonne} : du {periode[0]:%d/%m/%Y} au {periode[1]:%d/%m/%Y}"


def _archive(source, validation, contenu):
    return archive_projet(source["contenu"], source["nom"], validation["cleaned"], validation["rejects"],
                          rapport_markdown(contenu), validation["choix"], validation["log"], validation["plan"]["dictionary"],
                          rapport_html(contenu))


def _filtre(data, roles):
    """Filtrage facultatif sur une catégorie et une période (graphiques seulement).

    Retourne (lignes retenues, None) sans filtre, ou (lignes retenues, {texte, retenues, total}).
    """
    categories = [c for c, r in roles.items() if r == "Catégorie"]
    dates = [c for c, r in roles.items() if r == "Date" and data[c].notna().any()]
    if not categories and not dates:
        return data, None
    if not st.toggle("Filtrage", key="w_filtre_actif", help="Regarder les graphiques sur une partie des lignes "
                     "seulement. Les fichiers téléchargés ne changent pas."):
        return data, None
    specs, resumes = [], []
    with st.container(border=True, key="carte_filtrage"):
        gauche, droite = st.columns(2)
        if categories:
            with gauche:
                spec, resume = _filtre_categorie(data, categories)
                specs.append(spec)
                resumes.append(resume)
        if dates:
            with droite:
                spec, resume = _filtre_dates(data, dates[0])
                if spec:
                    specs.append(spec)
                    resumes.append(resume)
        retenues = apply_filters(data, specs)
        st.markdown(f"**{len(retenues):,} / {len(data):,} lignes retenues**".replace(",", " "))
        st.caption(f"Filtre actif : {' · '.join(resumes)}. Le filtre ne change pas les données téléchargées.")
    return retenues, {"texte": " · ".join(resumes), "retenues": len(retenues), "total": len(data)}


def ecran_visualiser():
    """Écran de l'étape 4."""
    etat = st.session_state
    validation = etat.get("validation")
    st.title("Vérifier vos données en graphiques", anchor=False)
    if validation is None:
        st.info("Validez d'abord vos corrections à l'étape Corriger, même si vous ne changez rien.", icon=":material/info:")
        st.button("Aller à l'étape Corriger", type="primary", icon=":material/arrow_back:", on_click=aller, args=("Corriger",))
        return
    st.caption("Ces graphiques servent à contrôler que les données corrigées sont plausibles avant l'analyse métier. "
               f"Ils portent sur les {validation['resultat']['gardees']:,} lignes gardées.".replace(",", " "))
    roles = _roles(validation)
    data, ignorees = cached(prepare, validation["cleaned"], roles, _dayfirst(validation))
    data, filtre = _filtre(data, roles)
    graphiques = [(g, None) for g in graphiques_controle(data, roles, ignorees)]
    graphiques += [(g, i) for i, spec in enumerate(etat.graphiques_ajoutes)
                   if (g := _graphique_ajoute(data, roles, spec, ignorees)) is not None]
    if not graphiques:
        st.info("Aucun graphique de contrôle possible : indiquez au moins une catégorie, un nombre ou une date à l'étape Comprendre.")
    for debut in range(0, len(graphiques), 2):
        for colonne, numero in zip(st.columns(2), range(debut, min(debut + 2, len(graphiques)))):
            graphique, retirer = graphiques[numero]
            with colonne:
                _carte(graphique, numero, retirer)
    _section_ajout(roles)
    _section_export(validation, [g for g, _ in graphiques], filtre)
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("Retour aux corrections", icon=":material/arrow_back:", on_click=aller, args=("Corriger",))
        st.button("Étape suivante : analyser", type="primary", icon=":material/arrow_forward:", icon_position="right",
                  on_click=aller, args=("Analyser",))
