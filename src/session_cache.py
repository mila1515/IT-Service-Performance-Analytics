"""Mémoïsation propre à la session : un calcul n'est refait que si ses entrées changent."""
import json

import streamlit as st

MAX_ENTRIES = 12


def cached(fn, data, *params):
    """`data` doit rester le même objet d'une interaction à l'autre (brut ou nettoyé en session).

    Les paramètres sont comparés par leur contenu JSON. Le résultat est partagé :
    l'appelant ne doit pas le modifier.
    """
    store = st.session_state.setdefault("session_cache", {})
    key = (fn.__module__, fn.__qualname__, id(data),
           json.dumps(params, sort_keys=True, default=str, ensure_ascii=False))
    if key not in store:
        while len(store) >= MAX_ENTRIES:
            store.pop(next(iter(store)))
        # La référence à `data` empêche la réutilisation de son id par un autre objet.
        store[key] = (data, fn(data, *params))
    return store[key][1]
