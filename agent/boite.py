"""Traitement des demandes de la boite Gmail : une execution de l'agent par email."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent

from agent.agent import Resultat, executer
from agent.config import Config
from agent.tools.gmail import BoiteGmail
from agent.tools.validation import Validation
from agent.traces import Trace

CONSIGNE = """\
Nouvelle demande recue dans la boite de l'agence.
message_id : {message_id}
client : {client_nom} <{client_email}>
indices du code : hors_perimetre_probable={hors}

{contenu}

Traite cette demande : redige le brouillon de reponse avec `creer_brouillon`,
ou appelle `transmettre_conseiller` si elle est hors perimetre."""


@dataclass
class Traitement:
    message_id: str
    client_email: str
    objet: str
    decision: str          # brouillon | transmis | transmis_automatiquement | aucune
    resultat: Resultat | None = None


def decision_depuis(resultat: Resultat) -> str:
    if "transmettre_conseiller" in resultat.outils_appeles:
        return "transmis"
    if "creer_brouillon" in resultat.outils_appeles:
        return "brouillon"
    return "aucune"


def traiter_boite(agent: Agent, boite: BoiteGmail, config: Config, validation: Validation,
                  maximum: int = 10) -> list[Traitement]:
    traitements = []
    for demande in boite.lire_demandes(maximum):
        if demande["statut"] == "transmis_automatiquement":
            trace = Trace(config.dossier_traces, "email-suspect")
            trace.ecrire({"type": "demande", "texte": f"{demande['objet']} ({demande['client_email']})"})
            trace.ecrire({"type": "erreur", "message": "Tentative d'injection detectee par le code : "
                          "email transmis a un conseiller sans etre montre au modele."})
            traitements.append(Traitement(demande["message_id"], demande["client_email"],
                                          demande["objet"], "transmis_automatiquement"))
            continue
        consigne = CONSIGNE.format(hors=demande["hors_perimetre_probable"] or "aucun", **demande)
        resultat = executer(agent, consigne, config, libelle="email", validation=validation)
        traitements.append(Traitement(demande["message_id"], demande["client_email"],
                                      demande["objet"], decision_depuis(resultat), resultat))
    return traitements
