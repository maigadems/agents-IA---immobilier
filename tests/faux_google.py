"""Faux services Google pour les tests (memes appels que googleapiclient, en memoire)."""

from __future__ import annotations

import copy
from datetime import datetime

import httplib2
from googleapiclient.errors import HttpError


class _Requete:
    def __init__(self, fonction):
        self._fonction = fonction

    def execute(self):
        return self._fonction()


def _erreur(statut: int) -> HttpError:
    return HttpError(httplib2.Response({"status": statut}), b"{}")


def _dt(valeur: str) -> datetime:
    return datetime.fromisoformat(valeur.replace("Z", "+00:00"))


class FauxCalendar:
    """Comme Google : un id deja utilise (meme annule) -> 409 ; delete -> status cancelled."""

    def __init__(self):
        self.evenements: dict[str, dict[str, dict]] = {}
        self.inserts = 0

    def _cal(self, cal_id):
        return self.evenements.setdefault(cal_id, {})

    # freebusy().query(body=...).execute()
    def freebusy(self):
        return self

    def query(self, body):
        def run():
            res = {}
            debut, fin = _dt(body["timeMin"]), _dt(body["timeMax"])
            for item in body["items"]:
                busy = [{"start": e["start"]["dateTime"], "end": e["end"]["dateTime"]}
                        for e in self._cal(item["id"]).values()
                        if e.get("status") != "cancelled"
                        and _dt(e["start"]["dateTime"]) < fin and debut < _dt(e["end"]["dateTime"])]
                res[item["id"]] = {"busy": busy}
            return {"calendars": res}
        return _Requete(run)

    # events().insert/get/update/patch/delete/list(...).execute()
    def events(self):
        return self

    def insert(self, calendarId, body):
        def run():
            if body["id"] in self._cal(calendarId):
                raise _erreur(409)
            self.inserts += 1
            ev = {**copy.deepcopy(body), "status": "confirmed", "htmlLink": f"https://cal/{body['id']}"}
            self._cal(calendarId)[body["id"]] = ev
            return ev
        return _Requete(run)

    def get(self, calendarId, eventId):
        def run():
            if eventId not in self._cal(calendarId):
                raise _erreur(404)
            return copy.deepcopy(self._cal(calendarId)[eventId])
        return _Requete(run)

    def update(self, calendarId, eventId, body):
        def run():
            self._cal(calendarId)[eventId] = {**copy.deepcopy(body), "id": eventId}
            return self._cal(calendarId)[eventId]
        return _Requete(run)

    def patch(self, calendarId, eventId, body):
        def run():
            self._cal(calendarId)[eventId].update(copy.deepcopy(body))
            return self._cal(calendarId)[eventId]
        return _Requete(run)

    def delete(self, calendarId, eventId):
        def run():
            self._cal(calendarId)[eventId]["status"] = "cancelled"
            return ""
        return _Requete(run)

    def list(self, calendarId, timeMin, timeMax, singleEvents=True):
        def run():
            debut, fin = _dt(timeMin), _dt(timeMax)
            items = [e for e in self._cal(calendarId).values()
                     if _dt(e["start"]["dateTime"]) < fin and debut < _dt(e["end"]["dateTime"])]
            return {"items": copy.deepcopy(items)}
        return _Requete(run)

    def actifs(self, cal_id):
        return [e for e in self._cal(cal_id).values() if e.get("status") != "cancelled"]
