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


def _b64(texte: str) -> str:
    import base64
    return base64.urlsafe_b64encode(texte.encode("utf-8")).decode()


class FauxGmail:
    """users().messages/drafts/labels/threads, avec une recherche simplifiee (in:inbox, -from:me, -label:)."""

    AGENCE = "agence.test@example.com"

    def __init__(self):
        self.msgs: dict[str, dict] = {}
        self.brouillons: dict[str, dict] = {}
        self.labels_: dict[str, str] = {"INBOX": "INBOX", "SENT": "SENT"}
        self.envois: list[dict] = []
        self._n = 0

    def _id(self, prefixe):
        self._n += 1
        return f"{prefixe}{self._n}"

    # --- alimentation des tests ---
    def recevoir(self, de: str, objet: str, corps: str, thread_id: str | None = None) -> str:
        mid = self._id("m")
        self.msgs[mid] = {
            "id": mid, "threadId": thread_id or f"t{mid}", "labelIds": ["INBOX"],
            "payload": {"mimeType": "text/plain", "body": {"data": _b64(corps)}, "headers": [
                {"name": "From", "value": de}, {"name": "Subject", "value": objet},
                {"name": "Message-ID", "value": f"<{mid}@client.test>"},
                {"name": "Date", "value": "Mon, 23 Nov 2026 09:00:00 +0000"}]},
        }
        return mid

    def noms_libelles(self, message_id):
        inverse = {v: k for k, v in self.labels_.items()}
        return {inverse[l] for l in self.msgs[message_id]["labelIds"]}

    # --- API ---
    def users(self):
        return self

    def labels(self):
        return _Espace(list=lambda userId: _Requete(lambda: {"labels": [
                           {"name": n, "id": i} for n, i in self.labels_.items()]}),
                       create=self._creer_label)

    def _creer_label(self, userId, body):
        def run():
            self.labels_[body["name"]] = f"Label_{len(self.labels_)}"
            return {"id": self.labels_[body["name"]], "name": body["name"]}
        return _Requete(run)

    def messages(self):
        return _Espace(list=self._lister, get=self._get, modify=self._modify)

    def _lister(self, userId, q, maxResults=10):
        def run():
            jetons = q.split()
            resultats = []
            for m in self.msgs.values():
                entetes = {h["name"].lower(): h["value"] for h in m["payload"]["headers"]}
                ok = True
                for j in jetons:
                    if j == "in:inbox":
                        ok &= "INBOX" in m["labelIds"]
                    elif j == "-from:me":
                        ok &= self.AGENCE not in entetes.get("from", "")
                    elif j.startswith("-label:"):
                        ok &= self.labels_.get(j[7:]) not in m["labelIds"]
                if ok:
                    resultats.append({"id": m["id"], "threadId": m["threadId"]})
            return {"messages": resultats[:maxResults]}
        return _Requete(run)

    def _get(self, userId, id, format="full", metadataHeaders=None):
        return _Requete(lambda: copy.deepcopy(self.msgs[id]))

    def _modify(self, userId, id, body):
        def run():
            labels = self.msgs[id]["labelIds"]
            for l in body.get("removeLabelIds", []):
                if l in labels:
                    labels.remove(l)
            for l in body.get("addLabelIds", []):
                if l not in labels:
                    labels.append(l)
            return self.msgs[id]
        return _Requete(run)

    def threads(self):
        def modify(userId, id, body):
            def run():
                for m in self.msgs.values():
                    if m["threadId"] == id:
                        self._modify(userId, m["id"], body).execute()
                return {"id": id}
            return _Requete(run)

        def get(userId, id, format="full"):
            return _Requete(lambda: {"id": id, "messages": [
                copy.deepcopy(m) for m in self.msgs.values() if m["threadId"] == id]})
        return _Espace(modify=modify, get=get)

    def drafts(self):
        return _Espace(create=self._creer_brouillon, get=self._get_brouillon, send=self._envoyer)

    def _creer_brouillon(self, userId, body):
        def run():
            import base64
            import email
            import email.policy
            brut = base64.urlsafe_b64decode(body["message"]["raw"])
            mime = email.message_from_bytes(brut, policy=email.policy.default)
            did = self._id("d")
            self.brouillons[did] = {
                "id": did, "mime": mime,
                "message": {"id": self._id("m"), "threadId": body["message"]["threadId"],
                            "payload": {"mimeType": "text/plain",
                                        "body": {"data": _b64(mime.get_content())},
                                        "headers": [{"name": k, "value": v} for k, v in mime.items()]}}}
            return {"id": did, "message": {"threadId": body["message"]["threadId"]}}
        return _Requete(run)

    def _get_brouillon(self, userId, id, format="full"):
        return _Requete(lambda: copy.deepcopy({k: v for k, v in self.brouillons[id].items() if k != "mime"}))

    def _envoyer(self, userId, body):
        def run():
            b = self.brouillons.pop(body["id"])
            self.envois.append(b)
            m = {**b["message"], "labelIds": ["SENT"]}
            self.msgs[m["id"]] = m
            return {"id": m["id"], "threadId": m["threadId"]}
        return _Requete(run)


class _Espace:
    def __init__(self, **methodes):
        self.__dict__.update(methodes)
