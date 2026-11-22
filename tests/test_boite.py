"""Ex 4 de bout en bout : 7 emails -> 5 brouillons, 0 envoi, hors perimetre et injection transmis."""

import json
import re
from datetime import datetime
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from agent.agent import construire_agent
from agent.boite import traiter_boite
from agent.catalogue_mcp import lecteur_fiches, toolset_catalogue
from agent.config import Config
from agent.tools.calendar import Agenda
from agent.tools.gmail import BoiteGmail
from agent.tools.outils_agenda import toolset_agenda
from agent.tools.outils_gmail import toolset_gmail
from agent.tools.regles import FUSEAU
from agent.tools.validation import Validation, toujours
from faux_google import FauxCalendar, FauxGmail

EMAILS = json.loads((Path(__file__).resolve().parent.parent / "evaluation" / "emails"
                     / "ex4_emails.json").read_text(encoding="utf-8"))
AGENDAS = {"Awa Diop": "awa@cal", "Moussa Ndiaye": "moussa@cal", "Fatou Sow": "fatou@cal"}


def modele_secretaire(messages, info):
    """Modele simule : transmet si le code signale un hors perimetre, sinon redige un brouillon."""
    consigne = next(p.content for m in messages for p in getattr(m, "parts", [])
                    if isinstance(p, UserPromptPart))
    message_id = re.search(r"message_id : (\S+)", consigne).group(1)
    deja = [p for m in messages if isinstance(m, ModelResponse) for p in m.parts
            if isinstance(p, ToolCallPart)]
    if deja:
        return ModelResponse(parts=[TextPart("traite")])
    if "hors_perimetre_probable=aucun" not in consigne:
        return ModelResponse(parts=[ToolCallPart("transmettre_conseiller",
                                                 {"message_id": message_id, "motif": "hors perimetre"})])
    return ModelResponse(parts=[ToolCallPart("creer_brouillon", {
        "message_id": message_id,
        "texte": "Bonjour,\nVoici nos biens disponibles et nos creneaux de visite."})])


def test_sept_emails_cinq_brouillons_aucun_envoi_non_valide():
    config, gmail, cal = Config(), FauxGmail(), FauxCalendar()
    validation = Validation(toujours(False))
    for e in EMAILS:
        gmail.recevoir(e["de"], e["objet"], e["corps"])
    boite = BoiteGmail(gmail, validation)
    agenda = Agenda(cal, AGENDAS, validation,
                    maintenant=lambda: datetime(2026, 11, 23, 8, tzinfo=FUSEAU))
    agent = construire_agent(
        config,
        [toolset_catalogue(config), toolset_agenda(agenda, lecteur_fiches(config)), toolset_gmail(boite)],
        modele=FunctionModel(modele_secretaire), avec_agenda=True, avec_gmail=True)

    traitements = traiter_boite(agent, boite, config, validation)

    decisions = {t.objet: t.decision for t in traitements}
    attendues = {e["objet"]: e["attendu"]["decision"] for e in EMAILS}
    assert decisions == attendues
    assert len(gmail.brouillons) == 5
    assert gmail.envois == []                       # aucun envoi sans validation
    assert traiter_boite(agent, boite, config, validation) == []   # rien n'est traite deux fois
