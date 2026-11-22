"""Acces controle a Google Calendar : creneaux libres, creer / deplacer / annuler une visite.

Garanties appliquees par le code :
  - regles de l'agence verifiees avant toute ecriture (regles.verifier_creneau) ;
  - validation humaine avant chaque creation, deplacement ou annulation ;
  - aucun doublon : disponibilite reverifiee juste avant l'ecriture ET identifiant d'evenement
    deterministe (agenda + heure de debut) -> Google refuse un second evenement (409).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, time, timedelta
from typing import Any, Callable

from googleapiclient.errors import HttpError

from agent.tools.creneaux import Plage, creneaux_libres
from agent.tools.regles import DUREE_VISITE, FUSEAU, RegleNonRespectee, en_dakar, verifier_creneau
from agent.tools.validation import Validation


def identifiant_visite(calendar_id: str, debut: datetime) -> str:
    """Identifiant Google valide (base32hex minuscule) et unique par agenda et horaire."""
    cle = f"{calendar_id}|{en_dakar(debut).isoformat()}".encode()
    return base64.b32hexencode(hashlib.sha1(cle).digest()).decode().lower().rstrip("=")


def _iso(moment: datetime) -> str:
    return en_dakar(moment).isoformat()


def _lire_date(valeur: dict) -> datetime:
    return en_dakar(datetime.fromisoformat(valeur["dateTime"].replace("Z", "+00:00")))


class Agenda:
    def __init__(
        self,
        service: Any,
        agendas: dict[str, str],
        validation: Validation,
        maintenant: Callable[[], datetime] = lambda: datetime.now(FUSEAU),
    ) -> None:
        self.service = service
        self.agendas = agendas
        self.validation = validation
        self.maintenant = maintenant

    # --- lecture ---------------------------------------------------------------
    def _agenda(self, conseiller: str) -> str:
        if conseiller not in self.agendas:
            raise ValueError(f"Aucun agenda configure pour le conseiller {conseiller!r}.")
        return self.agendas[conseiller]

    def occupations(self, conseiller: str, debut: datetime, fin: datetime) -> list[Plage]:
        cal_id = self._agenda(conseiller)
        corps = {"timeMin": _iso(debut), "timeMax": _iso(fin), "timeZone": "Africa/Dakar",
                 "items": [{"id": cal_id}]}
        reponse = self.service.freebusy().query(body=corps).execute()
        plages = reponse.get("calendars", {}).get(cal_id, {}).get("busy", [])
        return [(_lire_date({"dateTime": p["start"]}), _lire_date({"dateTime": p["end"]})) for p in plages]

    def lister_creneaux_libres(
        self,
        conseiller: str,
        debut: datetime,
        fin: datetime,
        heure_min: time | None = None,
        heure_max: time | None = None,
        nombre: int = 3,
    ) -> list[datetime]:
        occupes = self.occupations(conseiller, debut, fin)
        return creneaux_libres(debut, fin, occupes, self.maintenant(), nombre, heure_min, heure_max)

    def _est_libre(self, conseiller: str, debut: datetime, ignorer: str | None = None) -> bool:
        fin = debut + DUREE_VISITE
        if ignorer is None:
            return not self.occupations(conseiller, debut, fin)
        # deplacement : l'evenement deplace ne doit pas se bloquer lui-meme
        evenements = self.service.events().list(
            calendarId=self._agenda(conseiller), timeMin=_iso(debut), timeMax=_iso(fin),
            singleEvents=True).execute().get("items", [])
        return all(e["id"] == ignorer or e.get("status") == "cancelled" for e in evenements)

    def _alternatives(self, conseiller: str, debut: datetime) -> list[str]:
        jour = en_dakar(debut).replace(hour=0, minute=0)
        libres = self.lister_creneaux_libres(conseiller, jour, jour + timedelta(days=2))
        return [_iso(c) for c in libres]

    # --- ecriture (toujours apres validation) -------------------------------------
    def creer_visite(self, fiche: dict, debut: datetime, client_nom: str, client_email: str) -> dict:
        conseiller = fiche["conseiller"]
        cal_id = self._agenda(conseiller)
        try:
            debut = verifier_creneau(debut, self.maintenant())
        except RegleNonRespectee as exc:
            return {"statut": "regle_non_respectee", "message": str(exc)}
        if not self._est_libre(conseiller, debut):
            return {"statut": "creneau_pris", "message": "Ce creneau vient d'etre pris.",
                    "alternatives": self._alternatives(conseiller, debut)}

        fin = debut + DUREE_VISITE
        evenement = {
            "id": identifiant_visite(cal_id, debut),
            "summary": f"Visite {fiche['id']} - {client_nom}",
            "location": fiche["adresse"],
            "description": (f"Visite du bien {fiche['id']} ({fiche.get('type_bien', '')}, "
                            f"{fiche.get('quartier', '')}).\nClient : {client_nom} <{client_email}>\n"
                            f"Conseiller : {conseiller}"),
            "start": {"dateTime": _iso(debut), "timeZone": "Africa/Dakar"},
            "end": {"dateTime": _iso(fin), "timeZone": "Africa/Dakar"},
            "extendedProperties": {"private": {"bien_id": fiche["id"], "client_email": client_email}},
        }
        details = {"bien": fiche["id"], "adresse": fiche["adresse"], "conseiller": conseiller,
                   "debut": _iso(debut), "fin": _iso(fin), "client": f"{client_nom} <{client_email}>"}
        if not self.validation.demander("Creer une visite dans l'agenda", details):
            return {"statut": "refuse_par_conseiller", "message": "Le conseiller n'a pas valide la visite."}

        try:
            cree = self.service.events().insert(calendarId=cal_id, body=evenement).execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 409:
                raise
            existant = self.service.events().get(calendarId=cal_id, eventId=evenement["id"]).execute()
            if existant.get("status") != "cancelled":
                return {"statut": "doublon", "message": "Une visite existe deja sur ce creneau.",
                        "event_id": existant["id"]}
            # creneau d'une visite annulee : on reactive l'evenement avec les nouvelles infos
            cree = self.service.events().update(
                calendarId=cal_id, eventId=evenement["id"], body={**evenement, "status": "confirmed"}
            ).execute()
        return {"statut": "cree", "event_id": cree["id"], "conseiller": conseiller,
                "debut": _iso(debut), "fin": _iso(fin), "adresse": fiche["adresse"],
                "lien": cree.get("htmlLink")}

    def deplacer_visite(self, conseiller: str, event_id: str, nouveau_debut: datetime) -> dict:
        cal_id = self._agenda(conseiller)
        evenement = self.service.events().get(calendarId=cal_id, eventId=event_id).execute()
        try:
            nouveau_debut = verifier_creneau(nouveau_debut, self.maintenant())
        except RegleNonRespectee as exc:
            return {"statut": "regle_non_respectee", "message": str(exc)}
        if not self._est_libre(conseiller, nouveau_debut, ignorer=event_id):
            return {"statut": "creneau_pris", "alternatives": self._alternatives(conseiller, nouveau_debut)}
        fin = nouveau_debut + DUREE_VISITE
        details = {"visite": evenement.get("summary"), "adresse": evenement.get("location"),
                   "ancien_debut": evenement["start"]["dateTime"], "nouveau_debut": _iso(nouveau_debut)}
        if not self.validation.demander("Deplacer une visite", details):
            return {"statut": "refuse_par_conseiller"}
        maj = self.service.events().patch(calendarId=cal_id, eventId=event_id, body={
            "start": {"dateTime": _iso(nouveau_debut), "timeZone": "Africa/Dakar"},
            "end": {"dateTime": _iso(fin), "timeZone": "Africa/Dakar"},
        }).execute()
        return {"statut": "deplace", "event_id": maj["id"], "debut": _iso(nouveau_debut), "fin": _iso(fin)}

    def annuler_visite(self, conseiller: str, event_id: str) -> dict:
        cal_id = self._agenda(conseiller)
        evenement = self.service.events().get(calendarId=cal_id, eventId=event_id).execute()
        details = {"visite": evenement.get("summary"), "adresse": evenement.get("location"),
                   "debut": evenement["start"]["dateTime"]}
        if not self.validation.demander("Annuler une visite", details):
            return {"statut": "refuse_par_conseiller"}
        self.service.events().delete(calendarId=cal_id, eventId=event_id).execute()
        return {"statut": "annule", "event_id": event_id}
