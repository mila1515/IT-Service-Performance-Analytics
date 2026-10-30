"""L'appel à l'API GPT d'OpenAI, et rien d'autre : la clé vient de l'environnement ou du fichier `.env`.

La clé n'est jamais écrite dans le code, à l'écran, dans le rapport ni dans les messages d'erreur.
Pour changer de modèle sans toucher au code : variable `OPENAI_MODEL`.
"""
import json
import os
from pathlib import Path

FICHIER_ENV = Path(__file__).resolve().parents[2] / ".env"
MODELE_PAR_DEFAUT = "gpt-4o-mini"
DELAI_SECONDES = 60


class ErreurIA(Exception):
    """L'IA n'a pas pu répondre ; le message peut être affiché tel quel."""


def _lire_env(nom):
    valeur = os.environ.get(nom, "").strip()
    if valeur or not FICHIER_ENV.is_file():
        return valeur
    for ligne in FICHIER_ENV.read_text(encoding="utf-8-sig").splitlines():
        cle, signe, contenu = ligne.partition("=")
        if signe and cle.strip() == nom:
            return contenu.strip().strip("'\"")
    return ""


def cle_api():
    """La clé OpenAI, ou une chaîne vide si elle n'est pas configurée."""
    return _lire_env("OPENAI_API_KEY")


def modele():
    return _lire_env("OPENAI_MODEL") or MODELE_PAR_DEFAUT


def demander(messages):
    """Envoie les messages et retourne la réponse JSON de l'IA (dictionnaire). Lève `ErreurIA` en cas d'échec."""
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
    except ImportError as exc:
        raise ErreurIA("La bibliothèque openai n'est pas installée : pip install -r src/requirements.txt") from exc
    try:
        client = OpenAI(api_key=cle_api(), timeout=DELAI_SECONDES, max_retries=1)
        reponse = client.chat.completions.create(model=modele(), messages=messages,
                                                 response_format={"type": "json_object"})
        return json.loads(reponse.choices[0].message.content)
    except AuthenticationError as exc:
        raise ErreurIA("La clé API est refusée : vérifiez-la dans le fichier .env.") from exc
    except RateLimitError as exc:
        raise ErreurIA("Quota ou crédit OpenAI dépassé : vérifiez votre compte, ou réessayez dans un moment.") from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise ErreurIA("Impossible de joindre OpenAI : vérifiez la connexion, puis réessayez.") from exc
    except APIStatusError as exc:
        raise ErreurIA(f"OpenAI a refusé la demande (code {exc.status_code}). Vérifiez le modèle « {modele()} ».") from exc
    except (json.JSONDecodeError, TypeError, IndexError) as exc:
        raise ErreurIA("La réponse de l'IA est illisible : réessayez.") from exc
