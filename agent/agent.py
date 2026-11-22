"""Boucle de l'agent : modele + outils + limites d'etapes + traces."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import UsageLimits

from agent.config import Config
from agent.modele import construire_modele
from agent.prompts import prompt_systeme
from agent.tools.validation import Validation
from agent.traces import Trace, evenements_depuis_messages


@dataclass
class Resultat:
    texte: str
    trace: str
    appels_outils: int = 0
    tokens_entree: int = 0
    tokens_sortie: int = 0
    duree_s: float = 0.0
    erreur: str | None = None
    outils_appeles: list[str] = field(default_factory=list)
    # [{"outil", "arguments", "resultat", "ok"}] dans l'ordre : le pipeline y lit les creneaux
    # proposes et le brouillon cree, sans avoir a relire le texte du modele
    resultats_outils: list[dict] = field(default_factory=list)


def resultats_des_outils(evenements: list[dict]) -> list[dict]:
    """Associe chaque resultat (ou erreur) d'outil aux arguments de son appel."""
    arguments = {e["id"]: e["arguments"] for e in evenements if e["type"] == "appel_outil"}
    return [{"outil": e["outil"], "arguments": arguments.get(e["id"], {}),
             "resultat": e.get("resultat", e.get("erreur")), "ok": e["type"] == "resultat_outil"}
            for e in evenements if e["type"] in ("resultat_outil", "erreur_outil")]


def construire_agent(
    config: Config,
    toolsets: list[AbstractToolset],
    modele: Model | None = None,
    avec_agenda: bool = False,
    avec_gmail: bool = False,
) -> Agent:
    """Agent pydantic-ai. `retries` = nombre de tentatives quand un outil renvoie une erreur."""
    return Agent(
        modele or construire_modele(config),
        instructions=lambda: prompt_systeme(timezone=config.timezone, avec_agenda=avec_agenda,
                                            avec_gmail=avec_gmail),
        toolsets=toolsets,
        retries=config.retries_outils,
        name="agent-sama-ker",
    )


def executer(
    agent: Agent,
    demande: str,
    config: Config,
    libelle: str = "demande",
    validation: Validation | None = None,
) -> Resultat:
    """Execute une demande dans les limites de la boucle et ecrit la trace complete.

    Les decisions de validation humaine sont journalisees dans la meme trace.
    """
    trace = Trace(config.dossier_traces, libelle)
    if validation is not None:
        validation.trace = trace
    trace.ecrire({"type": "demande", "texte": demande})
    limites = UsageLimits(
        request_limit=config.max_etapes,
        tool_calls_limit=config.max_appels_outils,
    )
    debut = time.perf_counter()
    try:
        resultat = agent.run_sync(demande, usage_limits=limites)
    except UsageLimitExceeded as exc:
        message = f"Limite de la boucle atteinte ({exc}). Demande transmise a un conseiller."
        trace.ecrire({"type": "erreur", "message": message})
        return Resultat(texte=message, trace=str(trace.chemin), erreur="limite",
                        duree_s=time.perf_counter() - debut)

    duree = time.perf_counter() - debut
    messages = resultat.all_messages()
    evenements = evenements_depuis_messages(messages)
    for evenement in evenements:
        trace.ecrire(evenement)
    usage = resultat.usage
    outils = [p.tool_name for m in messages for p in getattr(m, "parts", [])
              if getattr(p, "part_kind", "") == "tool-call"]
    trace.ecrire({
        "type": "usage",
        "etapes": usage.requests,
        "appels_outils": usage.tool_calls,
        "tokens_entree": usage.input_tokens,
        "tokens_sortie": usage.output_tokens,
        "duree_s": round(duree, 2),
    })
    return Resultat(
        texte=str(resultat.output),
        trace=str(trace.chemin),
        appels_outils=usage.tool_calls,
        tokens_entree=usage.input_tokens,
        tokens_sortie=usage.output_tokens,
        duree_s=duree,
        outils_appeles=outils,
        resultats_outils=resultats_des_outils(evenements),
    )
