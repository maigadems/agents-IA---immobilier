"""Regles de visite de l'agence, appliquees par le code (pas laissees au modele)."""

from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from mcp_server.catalogue import CONSEILLERS

FUSEAU = ZoneInfo("Africa/Dakar")
DUREE_VISITE = timedelta(minutes=45)
OUVERTURE = time(9, 0)
FERMETURE = time(18, 0)
JOURS_OUVRES = {0, 1, 2, 3, 4, 5}  # lundi a samedi
PAS_CRENEAUX = timedelta(minutes=15)
DELAI_MINIMUM = timedelta(hours=2)  # pas de visite proposee dans les 2 prochaines heures


class RegleNonRespectee(ValueError):
    """Creneau contraire aux regles de l'agence (message lisible par le modele)."""


def en_dakar(moment: datetime) -> datetime:
    """Heure locale de Dakar ; une date sans fuseau est consideree comme heure de Dakar."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=FUSEAU)
    return moment.astimezone(FUSEAU)


def verifier_creneau(debut: datetime, maintenant: datetime | None = None) -> datetime:
    """Leve RegleNonRespectee si la visite [debut, debut+45 min] sort des regles."""
    debut = en_dakar(debut)
    fin = debut + DUREE_VISITE
    maintenant = en_dakar(maintenant or datetime.now(FUSEAU))
    if debut.weekday() not in JOURS_OUVRES:
        raise RegleNonRespectee("Pas de visite le dimanche : les visites ont lieu du lundi au samedi.")
    if debut.time() < OUVERTURE or fin.time() > FERMETURE or fin.date() != debut.date():
        raise RegleNonRespectee(
            "Les visites ont lieu entre 9h et 18h (debut au plus tard a 17h15, duree 45 min)."
        )
    if debut < maintenant + DELAI_MINIMUM:
        raise RegleNonRespectee("Ce creneau est passe ou trop proche (moins de 2 heures).")
    return debut


def agendas_conseillers() -> dict[str, str]:
    """Conseiller -> identifiant d'agenda Google (CALENDAR_ID_CONSEILLER_1..3 du .env)."""
    agendas = {}
    for i, nom in enumerate(CONSEILLERS, start=1):
        cal_id = os.getenv(f"CALENDAR_ID_CONSEILLER_{i}", "")
        if cal_id and not cal_id.startswith("changeme"):
            agendas[nom] = cal_id
    return agendas
