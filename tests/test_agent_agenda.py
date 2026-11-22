"""Ex 3 de bout en bout : agent + outils d'agenda + vrai serveur MCP + faux Google Calendar."""

import json
from datetime import datetime
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from agent.agent import construire_agent, executer
from agent.catalogue_mcp import lecteur_fiches, toolset_catalogue
from agent.config import Config
from agent.tools.calendar import Agenda
from agent.tools.outils_agenda import toolset_agenda
from agent.tools.regles import FUSEAU
from agent.tools.validation import Validation, toujours
from faux_google import FauxCalendar

MAINTENANT = datetime(2026, 11, 23, 8, 0, tzinfo=FUSEAU)
AGENDAS = {"Awa Diop": "awa@cal", "Moussa Ndiaye": "moussa@cal", "Fatou Sow": "fatou@cal"}


def scenario(*appels):
    def fonction(messages, info):
        n = sum(1 for m in messages if isinstance(m, ModelResponse))
        if n < len(appels):
            outil, args = appels[n]
            return ModelResponse(parts=[ToolCallPart(outil, args)])
        dernier = messages[-1].parts[-1]
        return ModelResponse(parts=[TextPart(json.dumps(
            dernier.content if isinstance(dernier, ToolReturnPart) else "", ensure_ascii=False))])
    return FunctionModel(fonction)


def preparer(modele, accord=True):
    config, faux = Config(), FauxCalendar()
    validation = Validation(toujours(accord))
    agenda = Agenda(faux, AGENDAS, validation, maintenant=lambda: MAINTENANT)
    agent = construire_agent(config, [toolset_catalogue(config),
                                      toolset_agenda(agenda, lecteur_fiches(config))],
                             modele=modele, avec_agenda=True)
    return config, faux, validation, agent


def test_agent_propose_trois_creneaux_jeudi_fin_d_apres_midi():
    config, faux, validation, agent = preparer(scenario(
        ("lister_creneaux_libres", {"bien_id": "SK-001", "date_debut": "2026-11-26",
                                    "date_fin": "2026-11-26", "heure_min": "15:00", "heure_max": "18:00"})))
    r = executer(agent, "jeudi prochain en fin d'apres-midi pour SK-001", config, validation=validation)
    reponse = json.loads(r.texte)
    assert reponse["conseiller"] == "Awa Diop" and len(reponse["creneaux"]) == 3
    assert reponse["creneaux"][0]["libelle"] == "jeudi 26/11 a 15h00"


def test_agent_cree_la_visite_validee_avec_adresse_du_catalogue():
    config, faux, validation, agent = preparer(scenario(
        ("creer_visite", {"bien_id": "SK-009", "debut": "2026-11-26T16:00",
                          "client_nom": "Mme Ndiaye", "client_email": "ndiaye@test.sn"})))
    r = executer(agent, "le client confirme jeudi 16h pour SK-009", config, validation=validation)
    [ev] = faux.actifs("fatou@cal")  # SK-009 est gere par Fatou Sow
    assert ev["location"] == "Route des Almadies, Almadies"
    traces = [json.loads(l) for l in Path(r.trace).read_text(encoding="utf-8").splitlines()]
    assert any(t["type"] == "validation" and t["accord"] for t in traces)


def test_agent_refus_conseiller_aucune_ecriture():
    config, faux, validation, agent = preparer(scenario(
        ("creer_visite", {"bien_id": "SK-001", "debut": "2026-11-26T16:00",
                          "client_nom": "X", "client_email": "x@test.sn"})), accord=False)
    r = executer(agent, "creer la visite", config, validation=validation)
    assert faux.inserts == 0 and "refuse_par_conseiller" in r.texte
