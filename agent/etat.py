"""Etat de chaque conversation client, d'un message a l'autre.

Une conversation = un fil Gmail (threadId). Quand le client repond, sa reponse arrive dans le
meme fil : le pipeline retrouve alors ce qui lui a ete propose (bien, creneaux) et reprend
au bon endroit. L'etat est enregistre dans un fichier JSON (ETAT_FICHIER), reecrit de facon
atomique a chaque changement : un arret du programme ne perd ni ne corrompt rien.

Etats possibles :
  brouillon_en_attente  reponse redigee, le conseiller n'a pas encore valide l'envoi
  creneaux_proposes     reponse envoyee avec des creneaux, on attend le choix du client
  attente_precisions    reponse envoyee avec des questions (demande incomplete)
  visite_confirmee      visite inscrite dans l'agenda et confirmation envoyee
  transmis              confie a un conseiller (hors perimetre, suspect, refus, erreurs)
  erreur                erreur technique, le message sera retraite au prochain passage
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

ETATS = ("brouillon_en_attente", "creneaux_proposes", "attente_precisions",
         "visite_confirmee", "transmis", "erreur")


@dataclass
class Conversation:
    thread_id: str
    client_email: str
    client_nom: str = ""
    etat: str = ""
    bien_id: str | None = None
    conseiller: str | None = None
    creneaux: list[str] = field(default_factory=list)     # debuts ISO proposes au client
    draft_id: str | None = None
    event_id: str | None = None
    tentatives: int = 0                                     # erreurs techniques successives
    messages_traites: list[str] = field(default_factory=list)
    historique: list[dict] = field(default_factory=list)

    @property
    def terminee(self) -> bool:
        return self.etat in ("visite_confirmee", "transmis")


class EtatConversations:
    """Stockage des conversations ; `chemin=None` garde tout en memoire (tests, evaluation)."""

    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = chemin
        self._conversations: dict[str, Conversation] = {}
        if chemin and chemin.exists():
            brut = json.loads(chemin.read_text(encoding="utf-8"))
            self._conversations = {t: Conversation(**c) for t, c in brut.items()}

    def get(self, thread_id: str) -> Conversation | None:
        return self._conversations.get(thread_id)

    def toutes(self) -> list[Conversation]:
        return list(self._conversations.values())

    def enregistrer(self, conversation: Conversation, etat: str, note: str = "", **champs) -> Conversation:
        if etat not in ETATS:
            raise ValueError(f"Etat inconnu : {etat!r}")
        for nom, valeur in champs.items():
            setattr(conversation, nom, valeur)
        conversation.etat = etat
        conversation.historique.append({"horodatage": datetime.now().isoformat(timespec="seconds"),
                                        "etat": etat, "note": note})
        self._conversations[conversation.thread_id] = conversation
        self._sauver()
        return conversation

    def _sauver(self) -> None:
        if self.chemin is None:
            return
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.chemin.with_suffix(".tmp")
        donnees = {t: asdict(c) for t, c in self._conversations.items()}
        provisoire.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(provisoire, self.chemin)
