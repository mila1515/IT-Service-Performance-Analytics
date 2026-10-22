"""Éditeur de dashboard : suggestions, filtres et disposition en grille."""
import json
import uuid

import altair as alt
import pandas as pd
import streamlit as st

from src.session_cache import cached
from src.visualization import (
    AGGREGATIONS, KINDS, PERIODS, ROLES, apply_filters, chart_data,
    infer_roles, prepare, suggestions, validate_configuration,
)

FILTER_MODES = ["Retenir les valeurs choisies", "Exclure les valeurs choisies"]
# Au-delà, exclusion par défaut avec une sélection vide (toutes les lignes gardées).
FILTER_KEEP_ALL_LIMIT = 50
# Au-delà, la liste déroulante devient trop lourde : saisie libre des valeurs.
FILTER_LIST_LIMIT = 1000


def reset_dashboard(roles, dayfirst=None):
    """Nouveaux rôles ou format de date : les graphiques et filtres existants ne sont plus valides."""
    state = st.session_state
    state.viz_roles = roles
    if dayfirst is not None:
        state.viz_dayfirst = dayfirst
    state.viz_charts = []
    state.viz_filters = []
    state.viz_revision = state.get("viz_revision", 0) + 1


def filter_editor(data, roles, prefix, initial=None):
    initial = {f["column"]: f for f in (initial or [])}
    columns = st.multiselect("Colonnes à filtrer", list(data), default=list(initial), key=f"{prefix}_columns")
    result = []
    for index, col in enumerate(columns):
        key = f"{prefix}_{index}_{col}"
        old = initial.get(col, {})
        role = roles[col]
        st.markdown(f"**{col}**")
        missing = st.checkbox("Inclure les valeurs manquantes", value=old.get("missing", True), key=f"{key}_missing")
        values = data[col].dropna()
        if role in ("Catégorie", "Identifiant"):
            options = sorted(values.astype(str).unique().tolist())
            # Beaucoup de valeurs : exclusion par défaut, sans présélectionner des milliers de valeurs.
            exclude = st.radio("Mode", FILTER_MODES, horizontal=True, key=f"{key}_mode",
                               index=int(old.get("exclude", len(options) > FILTER_KEEP_ALL_LIMIT))) == FILTER_MODES[1]
            # Les valeurs d'un filtre existant ne sont reprises que dans leur mode d'origine.
            same_mode = "values" in old and old.get("exclude", False) == exclude
            default = old["values"] if same_mode else [] if exclude else options
            label = "Valeurs à exclure" if exclude else "Valeurs retenues"
            if len(options) > FILTER_LIST_LIMIT:
                typed = st.text_area(f"{label} (une par ligne)", value="\n".join(default), key=f"{key}_values_{int(exclude)}")
                selected = list(dict.fromkeys(v.strip() for v in typed.splitlines() if v.strip()))
                unknown = len(set(selected) - set(options))
                st.caption(f"{len(options):,} valeurs distinctes : saisie libre au lieu d'une liste." + (f" {unknown} valeur(s) saisie(s) absente(s) des données." if unknown else ""))
            else:
                selected = st.multiselect(label, options, default=[v for v in default if v in options], key=f"{key}_values_{int(exclude)}")
            result.append({"column": col, "type": "Catégorie", "values": selected, "missing": missing, "exclude": exclude})
        elif values.empty:
            st.caption("Aucune valeur renseignée : seul le choix d'inclure les valeurs manquantes s'applique.")
            if role == "Date":
                result.append({"column": col, "type": role, "low": "1970-01-01", "high": "1970-01-01", "missing": missing})
            else:
                result.append({"column": col, "type": role, "low": 0., "high": 0., "missing": missing})
        elif role == "Date":
            low = st.date_input("Du", value=pd.Timestamp(old.get("low", values.min())).date(), key=f"{key}_low")
            high = st.date_input("Au (inclus)", value=pd.Timestamp(old.get("high", values.max())).date(), key=f"{key}_high")
            result.append({"column": col, "type": role, "low": low.isoformat(), "high": high.isoformat(), "missing": missing})
        else:
            low = st.number_input("Minimum inclus", value=float(old.get("low", values.min())), key=f"{key}_low")
            high = st.number_input("Maximum inclus", value=float(old.get("high", values.max())), key=f"{key}_high")
            result.append({"column": col, "type": role, "low": low, "high": high, "missing": missing})
    return result


def render_chart(data, spec, key="preview"):
    local = apply_filters(data, spec["filters"])
    frame, excluded = chart_data(local, spec)
    st.subheader(spec["title"])
    st.caption(f"{len(local):,} / {len(data):,} lignes retenues par les filtres du graphique (base : lignes après filtres globaux) · "
               f"{excluded:,} lignes sans valeur exploitable pour ce graphique.")
    with st.expander("Paramètres et filtres actifs"):
        st.json({k: v for k, v in spec.items() if k not in ("id", "reason")})
    if frame.empty:
        st.info("Aucune donnée exploitable pour cette sélection.")
        return
    kind = spec["kind"]
    if kind == "Histogramme":
        bins = pd.cut(frame["Valeur"], bins=30, duplicates="drop").value_counts(sort=False)
        frame = pd.DataFrame({"Début": [b.left for b in bins.index], "Fin": [b.right for b in bins.index], "Effectif": bins.to_numpy()})
        chart = alt.Chart(frame).mark_bar().encode(
            x=alt.X("Début:Q", title=spec["x"]), x2="Fin:Q",
            y=alt.Y("Effectif:Q"), tooltip=["Début:Q", "Fin:Q", "Effectif:Q"])
    elif kind == "Boîte à moustaches":
        values = frame["Valeur"]
        q1, median, q3 = values.quantile([.25, .5, .75])
        inside = values.between(q1-1.5*(q3-q1), q3+1.5*(q3-q1))
        summary = pd.DataFrame({"Bas": [values[inside].min()], "Q1": [q1], "Médiane": [median], "Q3": [q3], "Haut": [values[inside].max()]})
        base = alt.Chart(summary)
        chart = (base.mark_rule().encode(y=alt.Y("Bas:Q", title=spec["x"]), y2="Haut:Q")
                 + base.mark_bar(size=45).encode(y="Q1:Q", y2="Q3:Q", tooltip=["Q1:Q", "Médiane:Q", "Q3:Q"])
                 + base.mark_tick(color="white", size=45, thickness=2).encode(y="Médiane:Q"))
        outliers = frame.loc[~inside]
        st.caption(f"Quartiles calculés sur toutes les valeurs renseignées ; {len(outliers)} valeurs hors moustaches (1,5 × IQR).")
        if len(outliers) > 1000:
            outliers = outliers.sample(1000, random_state=42)
            st.caption("Affichage d'un échantillon reproductible de 1 000 valeurs hors moustaches.")
        if not outliers.empty:
            chart += alt.Chart(outliers).mark_circle(size=20, opacity=.4).encode(y="Valeur:Q")
        frame = summary
    elif kind == "Nuage de points":
        # Limitation explicite de l'affichage, pas des filtres ni des agrégations.
        if len(frame) > 5000:
            frame = frame.sample(5000, random_state=42)
            st.caption("Affichage d'un échantillon reproductible de 5 000 points.")
        chart = alt.Chart(frame).mark_circle(opacity=.55).encode(
            x=alt.X("X:Q", title=spec["x"]), y=alt.Y("Y:Q", title=spec["y"]), tooltip=["X:Q", "Y:Q"])
        st.caption("Une relation visuelle ne prouve pas une causalité.")
    elif kind == "Tableau croisé":
        st.caption("Effectifs par combinaison de catégories ; format long pour préserver les groupes à forte cardinalité.")
        st.dataframe(frame, hide_index=True)
        return
    else:
        axis_type = "T" if kind == "Courbe" else "N"
        base = alt.Chart(frame)
        chart = (base.mark_line(point=True) if kind == "Courbe" else base.mark_bar()).encode(
            x=alt.X(f"Groupe:{axis_type}", title=spec["x"], sort=None),
            y=alt.Y("Valeur:Q", title=f"{spec['agg']}" + (f" · {spec['y']}" if spec["agg"] != "Effectif" else "")),
            tooltip=[f"Groupe:{axis_type}", "Valeur:Q"])
        if kind == "Barres":
            st.caption(f"Au maximum {spec['limit']} groupes affichés ; tri : {spec['sort'].lower()}.")
    # Les statistiques sont calculées avant la limite d'affichage d'Altair.
    if len(frame) > 5000 and kind != "Nuage de points":
        st.warning("Plus de 5 000 lignes à tracer. Réduisez la période ou ajoutez un filtre ; tableau complet disponible ci-dessous.")
    else:
        st.altair_chart(chart, width="stretch", key=f"chart_{key}")
    with st.expander("Données du graphique"):
        st.dataframe(frame, hide_index=True)


def dashboard(data):
    st.header("Construire votre dashboard")
    st.caption("Suggestions fondées sur les rôles des colonnes. Confirmez leur sens métier avant de choisir un calcul.")
    state = st.session_state
    # Les rôles du dictionnaire font foi ; à défaut, ils sont proposés depuis les données.
    declared = {d["Colonne"]: d["Rôle"] for d in state.get("dictionary", [])}
    state.setdefault("viz_roles", declared if list(declared) == list(data) else infer_roles(data))
    state.setdefault("viz_dayfirst", False)
    state.setdefault("viz_charts", [])
    state.setdefault("viz_filters", [])
    state.setdefault("viz_revision", 0)
    prefix = f"viz_{state.viz_revision}"
    roles = state.viz_roles
    with st.expander("1 · Confirmer les rôles et le format des dates"):
        with st.form(f"{prefix}_roles"):
            proposed = {c: st.selectbox(str(c), ROLES, index=ROLES.index(roles[c]), key=f"{prefix}_role_{i}") for i, c in enumerate(data)}
            dayfirst = st.checkbox("Dates ambiguës : jour avant mois (03/04 = 3 avril)", value=state.viz_dayfirst)
            if st.form_submit_button("Appliquer les rôles"):
                if proposed != roles or dayfirst != state.viz_dayfirst:
                    reset_dashboard(proposed, dayfirst)
                    st.rerun()
        st.caption("Rôles initialisés depuis le dictionnaire de l'étape 2. Changer les rôles ou le format des dates réinitialise le dashboard. Les données nettoyées restent intactes. Les dates avec fuseau sont ramenées en UTC.")
    prepared, invalid = cached(prepare, data, roles, state.viz_dayfirst)
    if invalid:
        st.warning(f"Conversions impossibles ou nombres infinis traités comme manquants pour les graphiques uniquement : {invalid}")
        st.caption("Dates : un seul format est appliqué à toute la colonne (une année numérique est lue comme une année). Vérifiez l'option jour/mois si des dates ambiguës sont rejetées.")

    with st.expander("2 · Filtres globaux", expanded=bool(state.viz_filters)):
        global_filters = filter_editor(prepared, roles, f"{prefix}_global", state.viz_filters)
        if st.button("Appliquer les filtres globaux"):
            try:
                validate_configuration({"version": 1, "roles": roles, "charts": [], "filters": global_filters}, roles)
                state.viz_filters = global_filters
                st.success("Filtres appliqués à tous les graphiques.")
            except (ValueError, TypeError, KeyError) as exc:
                st.error(f"Filtres invalides : {exc}")
    filtered = apply_filters(prepared, state.viz_filters)
    st.write(f"**{len(filtered):,} / {len(prepared):,} lignes retenues par les filtres globaux.**")
    if state.viz_filters:
        st.json(state.viz_filters, expanded=False)

    options = suggestions(roles)
    existing = {f"saved_{c['id']}": c for c in state.viz_charts}
    starts = ["Personnaliser"] + [str(i) for i in range(len(options))] + list(existing)
    start_key = f"{prefix}_start"
    if state.get(start_key) not in starts:
        state.pop(start_key, None)
    with st.expander("3 · Suggestions et éditeur", expanded=not state.viz_charts or state.get(start_key) in existing):
        def label(value):
            if value in existing:
                return "Modifier · " + existing[value]["title"]
            return value if value == "Personnaliser" else options[int(value)]["title"]
        choice = st.selectbox("Point de départ", starts, index=1 if options else 0, format_func=label, key=start_key)
        template = existing[choice] if choice in existing else options[int(choice)] if choice != "Personnaliser" else {
            "kind": "Barres", "x": None, "y": None, "agg": "Effectif",
            "title": "Mon graphique", "width": "Demi", "period": "Mois",
            "sort": "Valeur décroissante", "limit": 20, "filters": []}
        editor = f"{prefix}_editor_{choice}"
        if "reason" in template:
            st.info(template["reason"])
        spec = None
        with st.expander("Personnaliser le graphique et ses filtres", expanded=choice == "Personnaliser" or choice in existing):
            kind = st.selectbox("Type de graphique", KINDS, index=KINDS.index(template["kind"]), key=f"{editor}_kind")
            editor += f"_{kind}"
            required = "Mesure" if kind in ("Histogramme", "Boîte à moustaches", "Nuage de points") else "Date" if kind == "Courbe" else "Catégorie"
            xs = [c for c, r in roles.items() if r == required]
            if not xs:
                st.info(f"Attribuez au moins une colonne au rôle « {required} » pour ce graphique.")
            else:
                x = st.selectbox("Axe / dimension", xs, index=xs.index(template["x"]) if template["x"] in xs else 0, key=f"{editor}_x")
                agg = st.selectbox("Calcul", list(AGGREGATIONS), index=list(AGGREGATIONS).index(template["agg"]), key=f"{editor}_agg") if kind in ("Barres", "Courbe") else "Effectif"
                y = None
                needs_y = kind in ("Nuage de points", "Tableau croisé") or agg != "Effectif"
                ys = [c for c, r in roles.items() if r == ("Catégorie" if kind == "Tableau croisé" else "Mesure") and c != x]
                if needs_y and not ys:
                    st.info("Une seconde colonne compatible est nécessaire. Confirmez les rôles ci-dessus.")
                else:
                    if needs_y:
                        y = st.selectbox("Seconde dimension" if kind == "Tableau croisé" else "Mesure", ys, index=ys.index(template["y"]) if template["y"] in ys else 0, key=f"{editor}_y_{x}")
                    title = st.text_input("Titre", value=template["title"], max_chars=200, key=f"{editor}_title")
                    period = st.selectbox("Période", list(PERIODS), index=list(PERIODS).index(template["period"]), key=f"{editor}_period") if kind == "Courbe" else "Mois"
                    sorts = ["Valeur décroissante", "Valeur croissante", "Groupe"]
                    sort = st.selectbox("Tri", sorts, index=sorts.index(template["sort"]), key=f"{editor}_sort") if kind == "Barres" else "Groupe"
                    limit = st.number_input("Nombre maximal de groupes", min_value=1, max_value=100, value=template["limit"], key=f"{editor}_limit") if kind == "Barres" else 20
                    st.caption("Les filtres du graphique s'ajoutent aux filtres globaux (intersection).")
                    local_filters = filter_editor(prepared, roles, f"{editor}_local", template["filters"])
                    spec = {"title": title, "kind": kind, "x": x, "y": y, "agg": agg, "period": period,
                            "sort": sort, "limit": int(limit), "width": template["width"], "filters": local_filters}
        if spec is not None:
            try:
                validate_configuration({"version": 1, "roles": roles, "filters": [], "charts": [spec]}, roles)
                render_chart(filtered, spec)
                if st.button("Mettre à jour le graphique" if choice in existing else "Ajouter au dashboard", type="primary"):
                    if choice in existing:
                        index = next(i for i, c in enumerate(state.viz_charts) if c["id"] == template["id"])
                        state.viz_charts[index] = dict(spec, id=template["id"])
                        st.rerun()
                    elif len(state.viz_charts) >= 30:
                        st.warning("Maximum de 30 graphiques atteint.")
                    else:
                        state.viz_charts.append(dict(spec, id=uuid.uuid4().hex))
                        st.rerun()
            except (ValueError, TypeError, KeyError) as exc:
                st.error(f"Configuration à corriger : {exc}")

    st.subheader("Votre dashboard")
    if not state.viz_charts:
        st.info("Ajoutez un graphique depuis les suggestions ou l'éditeur.")
    else:
        with st.expander("Modifier l'ordre, la largeur ou retirer un graphique"):
            ids = [c["id"] for c in state.viz_charts]
            labels = {c["id"]: f"{i+1} · {c['title']}" for i, c in enumerate(state.viz_charts)}
            selected = st.selectbox("Graphique", ids, format_func=labels.get)
            item = next(c for c in state.viz_charts if c["id"] == selected)
            with st.form(f"layout_{selected}"):
                new_width = st.selectbox("Largeur", ["Demi", "Pleine"], index=0 if item["width"] == "Demi" else 1)
                position = st.number_input("Position (1 = en haut)", min_value=1, max_value=len(ids), value=ids.index(selected)+1)
                if st.form_submit_button("Enregistrer la disposition"):
                    item["width"] = new_width
                    state.viz_charts.remove(item)
                    state.viz_charts.insert(int(position)-1, item)
                    st.rerun()
            st.caption("Deux demi-largeurs consécutives partagent une rangée. Titre, calcul et filtres : « Modifier ce graphique ».")
            left, right = st.columns(2)
            left.button("Modifier ce graphique", on_click=state.__setitem__, args=(start_key, f"saved_{selected}"))
            if right.button("Retirer ce graphique"):
                state.viz_charts = [c for c in state.viz_charts if c["id"] != selected]
                st.rerun()
        # Affichage dans l'ordre de la liste : deux demi-largeurs consécutives partagent une rangée.
        charts, i = state.viz_charts, 0
        while i < len(charts):
            paired = charts[i]["width"] == "Demi" and i+1 < len(charts) and charts[i+1]["width"] == "Demi"
            batch = charts[i:i+2] if paired else charts[i:i+1]
            containers = st.columns(2)[:len(batch)] if charts[i]["width"] == "Demi" else [st.container()]
            for container, spec in zip(containers, batch):
                with container:
                    with st.container(border=True):
                        render_chart(filtered, spec, key=spec["id"])
            i += len(batch)

    config = {"version": 1, "roles": roles, "dayfirst": state.viz_dayfirst, "filters": state.viz_filters, "charts": state.viz_charts}
    with st.expander("Sauvegarder ou restaurer le dashboard"):
        st.download_button("Exporter la configuration du dashboard", json.dumps(config, ensure_ascii=False, indent=2), "dashboard.json", "application/json")
        restore = st.file_uploader("Importer une configuration JSON", type=["json"], key=f"{prefix}_restore")
        st.caption("Pour restaurer, confirmez d'abord les mêmes rôles de colonnes et le même format des dates. Les filtres s'appliqueront aux données actuellement chargées.")
        if restore is not None and st.button("Restaurer le dashboard"):
            try:
                if len(restore.getvalue()) > 2_000_000:
                    raise ValueError("Configuration trop volumineuse (2 Mo maximum).")
                restored = validate_configuration(json.loads(restore.getvalue()), roles)
                if restored.get("dayfirst") != state.viz_dayfirst:
                    raise ValueError("Le format des dates ne correspond pas.")
                # Anciennes configurations : l'ordre par « row » devient l'ordre de la liste.
                ordered = sorted(restored["charts"], key=lambda c: c.get("row", 1))
                state.viz_charts = [dict({k: v for k, v in c.items() if k != "row"}, id=uuid.uuid4().hex) for c in ordered]
                state.viz_filters = restored["filters"]
                state.viz_revision += 1
                st.rerun()
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                st.error(f"Import refusé : {exc}")
