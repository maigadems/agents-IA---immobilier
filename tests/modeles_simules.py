"""Modele simule qui suit les etapes du pipeline, pour tester sans vrai modele.

Il lit la consigne, appelle les outils dans l'ordre (recherche, creneaux, brouillon) et
reutilise les vrais retours des outils : les biens et creneaux du brouillon viennent donc du
catalogue (serveur MCP) et de l'agenda (faux Google), comme avec un vrai modele bien eleve.
"""

from __future__ import annotations

import json
import re

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

QUARTIERS = ["Mermoz", "Ouakam", "Almadies", "Sacre-Coeur", "Point E", "Fann", "Plateau", "Yoff", "Ngor"]


def _consigne(messages) -> str:
    return next(p.content for m in messages if isinstance(m, ModelRequest) for p in m.parts
                if isinstance(p, UserPromptPart))


def _retours(messages) -> list[ToolReturnPart]:
    return [p for m in messages if isinstance(m, ModelRequest) for p in m.parts
            if isinstance(p, ToolReturnPart)]


def criteres(texte: str) -> dict:
    """Extraction tres simple du besoin, suffisante pour les tests."""
    message = texte.split("Message du client :", 1)[-1]
    args: dict = {}
    for q in QUARTIERS:
        if q.lower() in message.lower().replace("é", "e"):
            args["quartier"] = q
    pieces = re.search(r"\bF(\d)\b|(\d)\s*pi[eè]ces", message)
    if pieces:
        n = int(pieces.group(1) or pieces.group(2))
        args.update(pieces_min=n, pieces_max=n)
    for t in ("studio", "villa", "duplex"):
        if t in message.lower():
            args["type_bien"] = t
    budget = re.search(r"(\d{3})\s?000\s*F", message)
    if budget:
        args["loyer_max_fcfa"] = int(budget.group(1)) * 1000
    return args


def secretaire(date: str = "2026-11-26", heure_min: str = "15:00", heure_max: str = "18:00") -> FunctionModel:
    def fonction(messages, info):
        consigne = _consigne(messages)
        message_id = re.search(r"message_id : (\S+)", consigne).group(1)
        retours = _retours(messages)
        faits = [r.tool_name for r in retours]

        if "hors_perimetre_probable=aucun" not in consigne and "transmettre_conseiller" not in faits:
            return ModelResponse(parts=[ToolCallPart("transmettre_conseiller",
                                                     {"message_id": message_id, "motif": "hors perimetre"})])
        if "transmettre_conseiller" in faits or "creer_brouillon" in faits:
            return ModelResponse(parts=[TextPart("traite")])
        if "rechercher_biens" not in faits:
            return ModelResponse(parts=[ToolCallPart("rechercher_biens", criteres(consigne))])

        biens = next(r.content for r in retours if r.tool_name == "rechercher_biens")["biens"]
        if biens and "lister_creneaux_libres" not in faits:
            return ModelResponse(parts=[ToolCallPart("lister_creneaux_libres", {
                "bien_id": biens[0]["id"], "date_debut": date, "date_fin": date,
                "heure_min": heure_min, "heure_max": heure_max})])
        if not biens:
            texte = ("Bonjour,\nAucun bien de notre catalogue ne correspond a votre demande. "
                     "Pouvez-vous preciser le quartier et votre budget ?")
        else:
            creneaux = next(r.content for r in retours if r.tool_name == "lister_creneaux_libres")["creneaux"]
            lignes_biens = "\n".join(f"- {b['id']} : {b['quartier']}, {b['pieces']} pieces, "
                                     f"{b['loyer_fcfa']} F CFA" for b in biens[:3])
            lignes_creneaux = "\n".join(f"- {c['libelle']}" for c in creneaux)
            texte = (f"Bonjour,\nVoici nos biens :\n{lignes_biens}\n\nCreneaux de visite :\n"
                     f"{lignes_creneaux}\n\nRepondez avec le creneau choisi.")
        return ModelResponse(parts=[ToolCallPart("creer_brouillon", {"message_id": message_id, "texte": texte})])
    return FunctionModel(fonction)


def interprete(intention: str = "question", creneau: str | None = None) -> FunctionModel:
    """Modele d'interpretation qui renvoie toujours la meme intention."""
    def fonction(messages, info):
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, json.dumps(
            {"intention": intention, "creneau": creneau, "resume": ""}))])
    return FunctionModel(fonction)
