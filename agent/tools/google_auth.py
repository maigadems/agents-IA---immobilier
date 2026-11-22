"""Acces OAuth au compte Google de TEST de l'atelier (jamais un compte personnel).

Scopes demandes par l'agent, limites au strict necessaire :
  - gmail.modify           : lire les messages, poser les libelles, creer et envoyer les brouillons
                             (c'est le plus petit scope qui permet d'etiqueter un message)
  - calendar.events        : creer, deplacer, annuler les visites
  - calendar.freebusy      : connaitre les plages occupees des conseillers
Le scope `calendar` complet n'est utilise qu'une fois, par scripts/creer_agendas.py,
avec un jeton separe (token_setup.json) que l'on peut supprimer ensuite.

credentials.json et token*.json restent hors du depot (.gitignore).
"""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from agent.config import RACINE

SCOPES_AGENT = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
]
SCOPES_INSTALLATION = ["https://www.googleapis.com/auth/calendar"]


def _chemin(variable: str, defaut: str) -> Path:
    p = Path(os.getenv(variable, defaut))
    return p if p.is_absolute() else RACINE / p


def identifiants(scopes: list[str] = SCOPES_AGENT, fichier_jeton: Path | None = None) -> Credentials:
    """Charge le jeton, le rafraichit, ou lance le consentement OAuth dans le navigateur."""
    secrets = _chemin("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    jeton = fichier_jeton or _chemin("GOOGLE_TOKEN_FILE", "token.json")

    creds = None
    if jeton.exists():
        creds = Credentials.from_authorized_user_file(str(jeton), scopes)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not secrets.exists():
            raise FileNotFoundError(
                f"{secrets} introuvable : telechargez le client OAuth (application de bureau) "
                "depuis Google Cloud Console, voir README > Acces Google."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), scopes)
        creds = flow.run_local_server(port=0)
    jeton.write_text(creds.to_json(), encoding="utf-8")
    return creds


def service_calendar(creds: Credentials | None = None):
    return build("calendar", "v3", credentials=creds or identifiants(), cache_discovery=False)


def service_gmail(creds: Credentials | None = None):
    return build("gmail", "v1", credentials=creds or identifiants(), cache_discovery=False)
