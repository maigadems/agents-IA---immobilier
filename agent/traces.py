"""Traces de l'agent : chaque appel d'outil, ses arguments et son resultat, en JSON Lines.

Une trace = un fichier traces/<horodatage>-<id>.jsonl, une ligne par evenement :
  {"type": "demande"}  {"type": "appel_outil"}  {"type": "resultat_outil"}
  {"type": "erreur_outil"}  {"type": "reponse"}  {"type": "usage"}  {"type": "validation"}
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)


def _serialisable(valeur: Any) -> Any:
    try:
        json.dumps(valeur)
        return valeur
    except TypeError:
        if hasattr(valeur, "model_dump"):
            return valeur.model_dump(mode="json")
        return str(valeur)


def evenements_depuis_messages(messages: list[ModelMessage]) -> list[dict]:
    """Transforme l'historique pydantic-ai en evenements lisibles, dans l'ordre."""
    evenements: list[dict] = []
    etape = 0
    for message in messages:
        if isinstance(message, ModelResponse):
            etape += 1
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    evenements.append({
                        "type": "appel_outil",
                        "etape": etape,
                        "outil": part.tool_name,
                        "arguments": part.args_as_dict(),
                        "id": part.tool_call_id,
                    })
                elif isinstance(part, TextPart) and part.content.strip():
                    evenements.append({"type": "reponse", "etape": etape, "texte": part.content})
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    evenements.append({
                        "type": "resultat_outil",
                        "etape": etape,
                        "outil": part.tool_name,
                        "resultat": _serialisable(part.content),
                        "id": part.tool_call_id,
                    })
                elif isinstance(part, RetryPromptPart) and part.tool_name:
                    evenements.append({
                        "type": "erreur_outil",
                        "etape": etape,
                        "outil": part.tool_name,
                        "erreur": _serialisable(part.content),
                        "id": part.tool_call_id,
                    })
    return evenements


class Trace:
    """Journal d'un traitement, ecrit au fil de l'eau dans un fichier JSONL."""

    def __init__(self, dossier: Path, libelle: str = "demande") -> None:
        dossier.mkdir(parents=True, exist_ok=True)
        self.id = uuid.uuid4().hex[:8]
        horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.chemin = dossier / f"{horodatage}-{libelle}-{self.id}.jsonl"

    def ecrire(self, evenement: dict) -> None:
        ligne = {"horodatage": datetime.now().isoformat(timespec="seconds"), **evenement}
        with self.chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    def ecrire_messages(self, messages: list[ModelMessage]) -> None:
        for evenement in evenements_depuis_messages(messages):
            self.ecrire(evenement)


def resume_lisible(chemin: Path) -> str:
    """Affichage compact d'une trace, pour la console et la demo devant le jury."""
    lignes = []
    for brut in chemin.read_text(encoding="utf-8").splitlines():
        e = json.loads(brut)
        t = e["type"]
        if t == "demande":
            lignes.append(f"[demande] {e['texte']}")
        elif t == "appel_outil":
            lignes.append(f"  -> {e['outil']}({json.dumps(e['arguments'], ensure_ascii=False)})")
        elif t == "resultat_outil":
            texte = json.dumps(e["resultat"], ensure_ascii=False)
            lignes.append(f"  <- {e['outil']} : {texte[:200]}{'...' if len(texte) > 200 else ''}")
        elif t == "erreur_outil":
            lignes.append(f"  !! {e['outil']} : {e['erreur']}")
        elif t == "validation":
            lignes.append(f"  [validation] {e['action']} -> {'ACCORD' if e['accord'] else 'REFUS'}")
        elif t == "reponse":
            lignes.append(f"[reponse] {e['texte']}")
        elif t == "usage":
            lignes.append(f"[usage] {e}")
        elif t == "erreur":
            lignes.append(f"[erreur] {e['message']}")
    return "\n".join(lignes)
