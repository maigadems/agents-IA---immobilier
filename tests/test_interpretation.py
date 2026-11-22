"""Interpretation de la reponse du client par un modele simule."""

from datetime import datetime

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from agent.config import Config
from agent.interpretation import agent_interpretation, interpreter
from agent.tools.regles import FUSEAU

PROPOSES = [datetime(2026, 11, 26, 15, 0, tzinfo=FUSEAU), datetime(2026, 11, 26, 16, 45, tzinfo=FUSEAU)]


def modele_qui_repond(**sortie):
    def fonction(messages, info):
        outil = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(outil, sortie)])
    return FunctionModel(fonction)


def test_creneau_de_la_liste_accepte():
    agent = agent_interpretation(Config(), modele_qui_repond(
        intention="confirme_creneau", creneau="2026-11-26T16:45:00+00:00", resume="ok"))
    intention, usage = interpreter(agent, "c'est bon pour le second", PROPOSES)
    assert intention.intention == "confirme_creneau"
    assert intention.creneau == PROPOSES[1].isoformat()
    assert usage["appels_modele"] == 1


def test_creneau_invente_refuse():
    agent = agent_interpretation(Config(), modele_qui_repond(
        intention="confirme_creneau", creneau="2026-11-26T11:00:00+00:00"))
    intention, _ = interpreter(agent, "11h", PROPOSES)
    assert intention.intention == "question" and intention.creneau is None


def test_confirmation_sans_creneau_n_est_pas_une_confirmation():
    agent = agent_interpretation(Config(), modele_qui_repond(intention="confirme_creneau"))
    intention, _ = interpreter(agent, "oui", PROPOSES)
    assert intention.intention == "question"


def test_hors_perimetre():
    agent = agent_interpretation(Config(), modele_qui_repond(intention="hors_perimetre",
                                                             resume="negociation"))
    intention, _ = interpreter(agent, "je veux baisser le loyer", PROPOSES)
    assert intention.intention == "hors_perimetre"
