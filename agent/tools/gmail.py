"""Boite Gmail de l'agence : lire, rediger un brouillon dans le bon fil, envoyer apres validation.

Etat de chaque demande = un libelle Gmail :
  SK-A-traiter            demande lue, pas encore traitee
  SK-Attente-validation   brouillon pret, en attente du conseiller
  SK-Repondu              reponse envoyee apres validation
  SK-Transmis-conseiller  hors perimetre ou suspect : traite par un humain

L'agent ne peut pas envoyer sans validation : envoyer_brouillon() demande l'accord du conseiller
dans le code, quel que soit ce que le modele a decide.
"""

from __future__ import annotations

import base64
import html
import re
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

from agent.tools.securite import analyser, encapsuler
from agent.tools.validation import Validation

LIBELLES = {
    "a_traiter": "SK-A-traiter",
    "attente": "SK-Attente-validation",
    "repondu": "SK-Repondu",
    "transmis": "SK-Transmis-conseiller",
}

SIGNATURE = (
    "\n\nBien cordialement,\n"
    "L'equipe Sama Ker Immobilier\n"
    "Location de biens a Dakar - visites du lundi au samedi, 9h-18h"
)


def _decoder(donnees: str) -> str:
    return base64.urlsafe_b64decode(donnees + "=" * (-len(donnees) % 4)).decode("utf-8", errors="replace")


def _texte_html(contenu: str) -> str:
    contenu = re.sub(r"(?is)<(script|style).*?</\1>", " ", contenu)
    contenu = re.sub(r"(?i)<br\s*/?>|</p>", "\n", contenu)
    return html.unescape(re.sub(r"<[^>]+>", " ", contenu)).strip()


def extraire_corps(payload: dict) -> str:
    """Texte du message : text/plain en priorite, sinon text/html nettoye."""
    plain, htm = [], []

    def parcourir(partie: dict) -> None:
        type_mime = partie.get("mimeType", "")
        donnees = partie.get("body", {}).get("data")
        if donnees and type_mime == "text/plain":
            plain.append(_decoder(donnees))
        elif donnees and type_mime == "text/html":
            htm.append(_texte_html(_decoder(donnees)))
        for sous in partie.get("parts", []) or []:
            parcourir(sous)

    parcourir(payload)
    return ("\n".join(plain) or "\n".join(htm)).strip()


def _entetes(message: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}


class BoiteGmail:
    def __init__(self, service: Any, validation: Validation, signature: str = SIGNATURE) -> None:
        self.service = service
        self.validation = validation
        self.signature = signature
        self._ids: dict[str, str] | None = None
        self.suspects: set[str] = set()

    @property
    def _users(self):
        return self.service.users()

    # --- libelles -------------------------------------------------------------------
    def libelles(self) -> dict[str, str]:
        """Cree les libelles manquants ; renvoie cle -> id Gmail."""
        if self._ids is None:
            existants = {l["name"]: l["id"] for l in
                         self._users.labels().list(userId="me").execute().get("labels", [])}
            for nom in LIBELLES.values():
                if nom not in existants:
                    cree = self._users.labels().create(userId="me", body={
                        "name": nom, "labelListVisibility": "labelShow",
                        "messageListVisibility": "show"}).execute()
                    existants[nom] = cree["id"]
            self._ids = {cle: existants[nom] for cle, nom in LIBELLES.items()}
        return self._ids

    def _etiqueter(self, message_id: str, ajouter: str, retirer: tuple[str, ...] = ()) -> None:
        ids = self.libelles()
        self._users.messages().modify(userId="me", id=message_id, body={
            "addLabelIds": [ids[ajouter]], "removeLabelIds": [ids[r] for r in retirer]}).execute()

    # --- lecture ----------------------------------------------------------------------
    def lire_demandes(self, maximum: int = 10) -> list[dict]:
        """Demandes non traitees de la boite de reception (hors messages de l'agence)."""
        self.libelles()
        requete = ("in:inbox -from:me " + " ".join(
            f"-label:{LIBELLES[c]}" for c in ("attente", "repondu", "transmis")))
        liste = self._users.messages().list(userId="me", q=requete, maxResults=maximum).execute()
        demandes = []
        for ref in liste.get("messages", []):
            message = self._users.messages().get(userId="me", id=ref["id"], format="full").execute()
            entetes = _entetes(message)
            nom, email = parseaddr(entetes.get("from", ""))
            corps = extraire_corps(message.get("payload", {}))
            objet = entetes.get("subject", "")
            analyse = analyser(f"{objet}\n{corps}")
            demande = {"message_id": message["id"], "thread_id": message["threadId"],
                       "client_nom": nom or email, "client_email": email, "objet": objet,
                       "date": entetes.get("date", ""), **analyse}
            if analyse["suspect_injection"]:
                # jamais montre au modele : transmis directement a un conseiller
                self.suspects.add(message["id"])
                self._etiqueter(message["id"], "transmis", ("a_traiter",))
                demande.update(statut="transmis_automatiquement",
                               contenu="[contenu masque : tentative d'injection detectee]")
            else:
                self._etiqueter(message["id"], "a_traiter")
                demande.update(statut="a_traiter", contenu=encapsuler(corps, email, objet))
            demandes.append(demande)
        return demandes

    def historique_fil(self, thread_id: str, sauf: str | None = None) -> list[dict]:
        """Messages precedents du fil (ex 5) : le client et l'agence, dans l'ordre.

        Les textes du client restent des DONNEES encadrees ; un ancien message suspect est masque.
        """
        fil = self._users.threads().get(userId="me", id=thread_id, format="full").execute()
        historique = []
        for message in fil.get("messages", []):
            if message["id"] == sauf:
                continue
            entetes = _entetes(message)
            corps = extraire_corps(message.get("payload", {}))
            if "SENT" in message.get("labelIds", []):
                texte = corps.replace("\r\n", "\n").replace(self.signature.strip(), "").strip()
                historique.append({"auteur": "agence", "texte": texte})
                continue
            _, email = parseaddr(entetes.get("from", ""))
            if analyser(corps)["suspect_injection"]:
                corps = "[contenu masque : tentative d'injection detectee]"
            historique.append({"auteur": "client",
                               "texte": encapsuler(corps, email, entetes.get("subject", ""))})
        return historique

    # --- ecriture -----------------------------------------------------------------------
    def creer_brouillon(self, message_id: str, texte: str) -> dict:
        """Brouillon de reponse dans le fil du message d'origine (In-Reply-To / References)."""
        if message_id in self.suspects:
            return {"statut": "interdit", "message": "Message suspect : il a ete transmis a un conseiller."}
        original = self._users.messages().get(userId="me", id=message_id, format="metadata",
                                              metadataHeaders=["From", "Subject", "Message-ID",
                                                               "References", "Reply-To"]).execute()
        entetes = _entetes(original)
        objet = entetes.get("subject", "")
        reponse = EmailMessage()
        reponse["To"] = entetes.get("reply-to") or entetes.get("from", "")
        reponse["Subject"] = objet if objet.lower().startswith("re:") else f"Re: {objet}"
        if entetes.get("message-id"):
            reponse["In-Reply-To"] = entetes["message-id"]
            reponse["References"] = f"{entetes.get('references', '')} {entetes['message-id']}".strip()
        reponse.set_content(texte.rstrip() + self.signature)
        brut = base64.urlsafe_b64encode(reponse.as_bytes()).decode()
        brouillon = self._users.drafts().create(userId="me", body={
            "message": {"raw": brut, "threadId": original["threadId"]}}).execute()
        self._etiqueter(message_id, "attente", ("a_traiter",))
        return {"statut": "brouillon_cree", "draft_id": brouillon["id"],
                "thread_id": original["threadId"], "destinataire": reponse["To"]}

    def envoyer_brouillon(self, draft_id: str) -> dict:
        """Envoie un brouillon UNIQUEMENT si le conseiller le valide."""
        brouillon = self._users.drafts().get(userId="me", id=draft_id, format="full").execute()
        message = brouillon["message"]
        entetes = _entetes(message)
        details = {"a": entetes.get("to", ""), "objet": entetes.get("subject", ""),
                   "texte": extraire_corps(message.get("payload", {}))}
        if not self.validation.demander("Envoyer l'email au client", details):
            return {"statut": "refuse_par_conseiller", "message": "Brouillon conserve, non envoye."}
        envoye = self._users.drafts().send(userId="me", body={"id": draft_id}).execute()
        ids = self.libelles()
        self._users.threads().modify(userId="me", id=message["threadId"], body={
            "addLabelIds": [ids["repondu"]],
            "removeLabelIds": [ids["attente"], ids["a_traiter"]]}).execute()
        return {"statut": "envoye", "message_id": envoye.get("id"), "thread_id": message["threadId"]}

    def transmettre_conseiller(self, message_id: str, motif: str) -> dict:
        """Hors perimetre (reclamation, negociation, litige...) : un humain reprend la main."""
        self._etiqueter(message_id, "transmis", ("a_traiter", "attente"))
        return {"statut": "transmis", "message_id": message_id, "motif": motif}
