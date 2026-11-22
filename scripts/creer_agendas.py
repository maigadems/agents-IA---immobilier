"""Cree un agenda Google par conseiller sur le compte de test (a lancer une seule fois).

    python scripts/creer_agendas.py

Affiche les lignes CALENDAR_ID_CONSEILLER_* a copier dans .env. Idempotent : un agenda
deja present (meme nom) est reutilise. Utilise un jeton separe, token_setup.json, avec le
scope `calendar` complet ; il peut etre supprime une fois les agendas crees.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import RACINE  # noqa: E402
from agent.tools.google_auth import SCOPES_INSTALLATION, identifiants, service_calendar  # noqa: E402
from mcp_server.catalogue import CONSEILLERS  # noqa: E402

PREFIXE = "Visites - "


def main() -> int:
    creds = identifiants(SCOPES_INSTALLATION, RACINE / "token_setup.json")
    service = service_calendar(creds)

    existants = {c["summary"]: c["id"] for c in service.calendarList().list().execute().get("items", [])}
    print("# A copier dans .env :")
    for i, nom in enumerate(CONSEILLERS, start=1):
        titre = PREFIXE + nom
        cal_id = existants.get(titre)
        if cal_id is None:
            cal = service.calendars().insert(body={"summary": titre, "timeZone": "Africa/Dakar"}).execute()
            cal_id = cal["id"]
        print(f"CALENDAR_ID_CONSEILLER_{i}={cal_id}   # {nom}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
