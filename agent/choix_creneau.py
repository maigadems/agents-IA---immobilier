"""Reconnaitre, dans la reponse du client, le creneau qu'il choisit parmi ceux proposes (ex 5).

Le code essaie d'abord seul, sans modele : heure ("16h45", "16:45", "a 16h"), jour ("jeudi",
"26/11") ou rang ("le deuxieme creneau"). Il ne retient un creneau que s'il est le SEUL a
correspondre. Sinon (ambigu, refus, autre question), la decision revient au modele
(agent/interpretation.py) ou a un conseiller. Seuls les creneaux proposes peuvent etre choisis.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from agent.tools.regles import en_dakar

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
RANGS = {
    0: r"premier|premiere|1er|1ere",
    1: r"deuxieme|2e|2eme|second|seconde",
    2: r"troisieme|3e|3eme",
}
NOMS = r"(creneau|creneaux|horaire|proposition|option|choix|rendez-vous|rdv)"
REFUS = [
    r"aucun\w*\s+(de\s+ces\s+|des\s+)?(creneau|horaire|proposition)",
    r"ne\s+(me\s+)?(convien\w*|arrange\w*)\s+pas",
    r"pas\s+(disponible|libre|possible)",
    r"\bimpossible\b",
    r"autres?\s+(creneau|creneaux|date|dates|jour|jours|horaire|horaires|moment)",
    r"\bannul\w*",
]


@dataclass
class Choix:
    statut: str                       # choisi | ambigu | refus | aucun
    creneau: datetime | None = None
    candidats: list[datetime] = field(default_factory=list)


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[ \t]+", " ", texte)


def sans_citation(texte: str) -> str:
    """Retire le message cite en dessous de la reponse (lignes "> ..." et "Le ... a ecrit :")."""
    lignes = []
    for ligne in texte.splitlines():
        brute = ligne.strip()
        if re.match(r"^(le|on)\s.+(a\s+ecrit|a\s+écrit|wrote)\s*:\s*$", brute, re.IGNORECASE):
            break
        if brute.startswith(">"):
            continue
        lignes.append(ligne)
    return "\n".join(lignes)


def _heures(texte: str) -> list[tuple[int, int]]:
    trouvees = []
    for h, m in re.findall(r"\b([01]?\d|2[0-3])\s*(?:h|:|heures?)\s*([0-5]\d)?\b", texte):
        trouvees.append((int(h), int(m or 0)))
    return trouvees


def _jours(texte: str) -> tuple[set[int], set[tuple[int, int]]]:
    semaine = {i for i, j in enumerate(JOURS) if re.search(rf"\b{j}\b", texte)}
    dates = {(int(j), int(m)) for j, m in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", texte)}
    return semaine, dates


def _rang(texte: str) -> int | None:
    for indice, motif in RANGS.items():
        if re.search(rf"\b({motif})\s+{NOMS}\b", texte) or re.search(rf"\b{NOMS}\s+(n°|no|numero)?\s*{indice + 1}\b", texte):
            return indice
    if re.search(rf"\b(dernier|derniere)\s+{NOMS}\b", texte):
        return -1
    return None


def reconnaitre(texte: str, proposes: list[datetime]) -> Choix:
    """Choix du client parmi `proposes`, ou statut ambigu / refus / aucun."""
    texte = normaliser(sans_citation(texte))
    proposes = [en_dakar(c) for c in proposes]
    if not proposes:
        return Choix("aucun")
    choix = _choix(texte, proposes)
    if any(re.search(m, texte) for m in REFUS):
        # "16h ne me convient pas" : un refus et une heure a la fois -> on ne tranche pas seul
        return Choix("ambigu", None, choix.candidats) if choix.statut == "choisi" else Choix("refus")
    return choix


def _choix(texte: str, proposes: list[datetime]) -> Choix:
    rang = _rang(texte)
    if rang is not None and -len(proposes) <= rang < len(proposes):
        return Choix("choisi", proposes[rang], [proposes[rang]])

    candidats = list(proposes)
    heures = _heures(texte)
    if heures:
        candidats = [c for c in candidats if any(c.hour == h and c.minute == m for h, m in heures)]
    semaine, dates = _jours(texte)
    if semaine:
        candidats = [c for c in candidats if c.weekday() in semaine]
    if dates:
        candidats = [c for c in candidats if (c.day, c.month) in dates]

    if not (heures or semaine or dates):
        return Choix("aucun")
    if len(candidats) == 1:
        return Choix("choisi", candidats[0], candidats)
    return Choix("ambigu", None, candidats)
