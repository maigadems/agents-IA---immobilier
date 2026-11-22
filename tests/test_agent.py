"""Boucle de l'agent testee avec un modele simule (FunctionModel) et le vrai serveur MCP."""

import json
from dataclasses import replace
from pathlib import Path

from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from agent.agent import construire_agent, executer
from agent.catalogue_mcp import toolset_catalogue
from agent.config import Config


def _evenements(resultat):
    return [json.loads(l) for l in Path(resultat.trace).read_text(encoding="utf-8").splitlines()]


def modele_scenario(*appels):
    """Le modele appelle les outils donnes un par un, puis repond avec le dernier retour."""
    def fonction(messages, info):
        n = sum(1 for m in messages if isinstance(m, ModelResponse))
        if n < len(appels):
            outil, args = appels[n]
            return ModelResponse(parts=[ToolCallPart(outil, args)])
        dernier = messages[-1].parts[-1]
        contenu = dernier.content if isinstance(dernier, (ToolReturnPart, RetryPromptPart)) else ""
        return ModelResponse(parts=[TextPart(f"fin: {json.dumps(contenu, ensure_ascii=False, default=str)}")])
    return FunctionModel(fonction)


def test_trace_contient_appel_arguments_et_resultat():
    config = Config()
    args = {"quartier": "Mermoz", "pieces_min": 3, "pieces_max": 3, "loyer_max_fcfa": 400000}
    agent = construire_agent(config, [toolset_catalogue(config)],
                             modele=modele_scenario(("rechercher_biens", args)))
    r = executer(agent, "un F3 a Mermoz a moins de 400 000 F", config)

    ev = _evenements(r)
    appel = next(e for e in ev if e["type"] == "appel_outil")
    retour = next(e for e in ev if e["type"] == "resultat_outil")
    assert appel["outil"] == "rechercher_biens" and appel["arguments"] == args
    assert retour["resultat"]["biens"][0]["id"] == "SK-001"
    assert ev[-1]["type"] == "usage" and ev[-1]["appels_outils"] == 1
    assert r.appels_outils == 1 and r.erreur is None


def test_erreur_outil_renvoyee_au_modele_puis_correction():
    config = Config()
    agent = construire_agent(config, [toolset_catalogue(config)], modele=modele_scenario(
        ("detail_bien", {"bien_id": "SK-999"}),
        ("detail_bien", {"bien_id": "SK-002"}),
    ))
    r = executer(agent, "detail du bien SK-999", config)
    types = [e["type"] for e in _evenements(r)]
    assert "erreur_outil" in types and "resultat_outil" in types
    assert "SK-002" in r.texte


def test_limite_d_etapes_transmet_a_un_conseiller():
    config = replace(Config(), max_etapes=2)
    boucle_infinie = FunctionModel(
        lambda m, i: ModelResponse(parts=[ToolCallPart("infos_agence", {})]))
    agent = construire_agent(config, [toolset_catalogue(config)], modele=boucle_infinie)
    r = executer(agent, "boucle", config)
    assert r.erreur == "limite" and "conseiller" in r.texte
