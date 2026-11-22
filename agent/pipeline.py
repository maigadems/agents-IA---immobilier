"""Pipeline complet (ex 5) : de l'email recu a la visite inscrite dans l'agenda.

Premier message d'un fil (nouvelle demande) :
    lecture -> modele (besoin, catalogue, creneaux libres, brouillon) -> VALIDATION 1 -> envoi
Reponse du client dans le meme fil (creneaux deja proposes) :
    creneau choisi (code, sinon modele) -> VALIDATION 2 (visite + confirmation) -> agenda + envoi

L'etat de chaque conversation est garde par fil Gmail (agent/etat.py). Le modele ne peut ni
envoyer ni ecrire dans l'agenda : ces actions sont faites par ce code, apres validation.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from pydantic_ai import Agent

from agent.agent import Resultat, executer
from agent.choix_creneau import reconnaitre
from agent.config import Config
from agent.courriers import texte_alternatives, texte_confirmation
from agent.etat import Conversation, EtatConversations
from agent.interpretation import interpreter
from agent.tools.calendar import Agenda
from agent.tools.gmail import BoiteGmail
from agent.tools.regles import DUREE_VISITE
from agent.tools.validation import Validation
from agent.traces import Trace

LecteurFiche = Callable[[str], Awaitable[dict]]

CONSIGNE_NOUVELLE = """\
Nouvelle demande recue dans la boite de l'agence.
message_id : {message_id}
client : {client_nom} <{client_email}>
indices du code : hors_perimetre_probable={hors}
{historique}
Message du client :
{contenu}

Traite cette demande en suivant les etapes, dans l'ordre :
1. Comprends le besoin (type de bien, quartier, pieces, budget, periode de visite).
2. Cherche les biens avec `rechercher_biens`.
3. Pour le bien qui correspond le mieux, appelle `lister_creneaux_libres` sur la periode
   demandee (sans periode : les 3 prochains jours a partir de demain).
4. Appelle `creer_brouillon` : les biens (identifiant, quartier, pieces, loyer), les creneaux
   (libelles exacts), et demande au client de repondre avec le creneau choisi.
Demande incomplete : brouillon avec 1 ou 2 questions precises. Hors perimetre :
`transmettre_conseiller`, sans brouillon. N'envoie rien toi-meme."""

ACTION_ENVOI = "Envoyer l'email au client"
MAX_TENTATIVES = 3


@dataclass
class Bilan:
    """Ce qu'est devenu un email : sert a l'affichage, aux tests et a l'evaluation (ex 6)."""
    message_id: str
    thread_id: str
    client_email: str
    objet: str
    etape: str                       # nouvelle_demande | suite
    decision: str                    # envoye | refuse | transmis | transmis_automatiquement | erreur ...
    etat: str = ""
    biens: list[str] = field(default_factory=list)
    creneaux: list[str] = field(default_factory=list)
    validations: int = 0
    appels_outils: int = 0
    tokens_entree: int = 0
    tokens_sortie: int = 0
    duree_s: float = 0.0
    traces: list[str] = field(default_factory=list)
    detail: str = ""


def _dernier(resultat: Resultat, outil: str) -> dict | None:
    """Dernier retour reussi d'un outil dans l'execution."""
    for r in reversed(resultat.resultats_outils):
        if r["outil"] == outil and r["ok"] and isinstance(r["resultat"], dict):
            return r
    return None


def biens_cites(texte: str) -> list[str]:
    return sorted(set(re.findall(r"\bSK-\d{3}\b", texte.upper())))


class Pipeline:
    def __init__(
        self,
        agent: Agent,
        boite: BoiteGmail,
        agenda: Agenda,
        fiche_bien: LecteurFiche,
        etat: EtatConversations,
        config: Config,
        validation: Validation,
        interpretation: Agent | None = None,
    ) -> None:
        self.agent = agent
        self.boite = boite
        self.agenda = agenda
        self.fiche_bien = fiche_bien
        self.etat = etat
        self.config = config
        self.validation = validation
        self.interpretation = interpretation

    # --- boucle ----------------------------------------------------------------------
    def passe(self, maximum: int = 10) -> list[Bilan]:
        """Une lecture de la boite : chaque nouveau message est traite jusqu'au bout."""
        return [self.traiter(demande) for demande in self.boite.lire_demandes(maximum)]

    def traiter(self, demande: dict) -> Bilan:
        debut = time.perf_counter()
        nb_validations = len(self.validation.journal)
        conv = self.etat.get(demande["thread_id"]) or Conversation(
            demande["thread_id"], demande["client_email"], demande["client_nom"])
        try:
            if conv.etat == "creneaux_proposes" and demande["statut"] != "transmis_automatiquement":
                bilan = self._suite(demande, conv)
            else:
                bilan = self._nouvelle(demande, conv)
            conv.tentatives = 0
        except Exception as exc:  # modele injoignable, serveur MCP arrete, API Google en erreur...
            bilan = self._erreur(demande, conv, exc)
        # questions reellement posees au conseiller (les ecritures couvertes ne comptent pas)
        bilan.validations = sum(1 for v in self.validation.journal[nb_validations:]
                                if "couvert_par" not in v)
        bilan.duree_s = time.perf_counter() - debut
        bilan.etat = conv.etat
        return bilan

    # --- premier message : reponse avec biens et creneaux -------------------------------
    def _nouvelle(self, demande: dict, conv: Conversation) -> Bilan:
        bilan = Bilan(demande["message_id"], demande["thread_id"], demande["client_email"],
                      demande["objet"], "suite" if conv.historique else "nouvelle_demande", "")
        if demande["statut"] == "transmis_automatiquement":
            trace = Trace(self.config.dossier_traces, "email-suspect")
            trace.ecrire({"type": "demande", "texte": f"{demande['objet']} ({demande['client_email']})"})
            trace.ecrire({"type": "erreur", "message": "Tentative d'injection detectee par le code : "
                          "email transmis a un conseiller sans etre montre au modele."})
            self.etat.enregistrer(conv, "transmis", "suspect d'injection")
            bilan.decision, bilan.traces = "transmis_automatiquement", [str(trace.chemin)]
            return bilan

        historique = self._historique(demande)
        consigne = CONSIGNE_NOUVELLE.format(hors=demande["hors_perimetre_probable"] or "aucun",
                                            historique=historique, **demande)
        resultat = executer(self.agent, consigne, self.config, libelle="pipeline",
                            validation=self.validation)
        self._mesurer(bilan, resultat)

        if _dernier(resultat, "transmettre_conseiller"):
            self.etat.enregistrer(conv, "transmis", "hors perimetre (modele)")
            bilan.decision = "transmis"
            return bilan

        brouillon = _dernier(resultat, "creer_brouillon")
        if not brouillon or brouillon["resultat"].get("statut") != "brouillon_cree":
            self.boite.transmettre_conseiller(demande["message_id"], "aucune reponse preparee")
            self.etat.enregistrer(conv, "transmis", "le modele n'a pas prepare de reponse")
            bilan.decision, bilan.detail = "transmis", resultat.texte[:200]
            return bilan

        creneaux = _dernier(resultat, "lister_creneaux_libres")
        texte = brouillon["arguments"].get("texte", "")
        bilan.biens = biens_cites(texte)
        champs: dict[str, Any] = {"draft_id": brouillon["resultat"]["draft_id"]}
        if creneaux and creneaux["resultat"].get("creneaux"):
            champs.update(bien_id=creneaux["resultat"]["bien_id"],
                          conseiller=creneaux["resultat"]["conseiller"],
                          creneaux=[c["debut"] for c in creneaux["resultat"]["creneaux"]])
            bilan.creneaux = champs["creneaux"]
        self.etat.enregistrer(conv, "brouillon_en_attente", "brouillon pret", **champs)
        return self._envoyer(demande, conv, bilan, champs["draft_id"],
                             "creneaux_proposes" if conv.creneaux else "attente_precisions")

    def _envoyer(self, demande: dict, conv: Conversation, bilan: Bilan, draft_id: str,
                 etat_si_envoye: str) -> Bilan:
        """VALIDATION : le conseiller relit le brouillon avant tout envoi."""
        envoi = self.boite.envoyer_brouillon(draft_id)
        if envoi["statut"] == "envoye":
            conv.messages_traites.append(demande["message_id"])
            self.etat.enregistrer(conv, etat_si_envoye, "reponse envoyee apres validation")
            bilan.decision = "envoye"
        else:
            self.etat.enregistrer(conv, "brouillon_en_attente", "envoi refuse par le conseiller")
            bilan.decision = "refuse"
        return bilan

    # --- reponse du client : confirmation d'un creneau ----------------------------------
    def _suite(self, demande: dict, conv: Conversation) -> Bilan:
        bilan = Bilan(demande["message_id"], demande["thread_id"], demande["client_email"],
                      demande["objet"], "suite", "")
        trace = Trace(self.config.dossier_traces, "confirmation")
        self.validation.trace = trace
        bilan.traces.append(str(trace.chemin))
        trace.ecrire({"type": "demande", "texte": demande["contenu"], "etat": conv.etat,
                      "bien_id": conv.bien_id, "creneaux_proposes": conv.creneaux})

        proposes = [datetime.fromisoformat(c) for c in conv.creneaux]
        choix = reconnaitre(demande["contenu"], proposes)
        trace.ecrire({"type": "interpretation", "source": "code", "statut": choix.statut,
                      "creneau": choix.creneau.isoformat() if choix.creneau else None})
        creneau, intention = choix.creneau, None
        if choix.statut != "choisi" and self.interpretation is not None:
            reponse, conso = interpreter(self.interpretation, demande["contenu"], proposes)
            bilan.tokens_entree += conso["tokens_entree"]
            bilan.tokens_sortie += conso["tokens_sortie"]
            trace.ecrire({"type": "interpretation", "source": "modele", **reponse.model_dump(), **conso})
            intention = reponse.intention
            if reponse.creneau:
                creneau = datetime.fromisoformat(reponse.creneau)

        if creneau is not None:
            return self._confirmer(demande, conv, bilan, creneau, trace)
        if intention == "hors_perimetre":
            self.boite.transmettre_conseiller(demande["message_id"], "hors perimetre (reponse du client)")
            self.etat.enregistrer(conv, "transmis", "reponse du client hors perimetre")
            bilan.decision = "transmis"
            return bilan
        if intention == "annule":
            self.boite.transmettre_conseiller(demande["message_id"], "le client renonce a la visite")
            self.etat.enregistrer(conv, "transmis", "le client renonce")
            bilan.decision = "transmis"
            return bilan
        # autres creneaux, question, choix ambigu : le modele repond avec tout le fil en contexte
        nouvelle = self._nouvelle(demande, conv)
        nouvelle.traces = bilan.traces + nouvelle.traces
        nouvelle.etape = "suite"
        return nouvelle

    def _confirmer(self, demande: dict, conv: Conversation, bilan: Bilan, creneau: datetime,
                   trace: Trace) -> Bilan:
        """VALIDATION 2 : une seule question au conseiller pour la visite ET la confirmation."""
        fiche = asyncio.run(self.fiche_bien(conv.bien_id))
        bilan.biens, bilan.creneaux = [fiche["id"]], [creneau.isoformat()]
        if self.agenda.occupations(fiche["conseiller"], creneau, creneau + DUREE_VISITE):
            # pris entre-temps : inutile de deranger le conseiller pour une visite impossible
            trace.ecrire({"type": "erreur", "message": f"creneau {creneau.isoformat()} pris entre-temps"})
            return self._proposer_autres(demande, conv, bilan, fiche, creneau, {"statut": "creneau_pris"})
        texte =texte_confirmation(fiche, creneau, demande["client_nom"])
        details = {"bien": fiche["id"], "adresse": fiche["adresse"], "conseiller": fiche["conseiller"],
                   "debut": creneau.isoformat(), "client": f"{demande['client_nom']} <{demande['client_email']}>",
                   "email_de_confirmation": texte}
        with self.validation.accord_groupe("Creer la visite et envoyer la confirmation", details,
                                           ("Creer une visite dans l'agenda", ACTION_ENVOI)) as accord:
            if not accord:
                self.boite.transmettre_conseiller(demande["message_id"], "visite non validee par le conseiller")
                self.etat.enregistrer(conv, "transmis", "visite refusee par le conseiller")
                bilan.decision = "refuse"
                return bilan
            visite = self.agenda.creer_visite(fiche, creneau, demande["client_nom"], demande["client_email"])
            trace.ecrire({"type": "resultat_outil", "outil": "creer_visite", "resultat": visite})
            if visite["statut"] == "doublon" and self._visite_du_client(fiche, visite, demande):
                # deja inscrite pour CE client (traitement interrompu puis repris) : on confirme
                visite = {**visite, "statut": "cree"}
            if visite["statut"] == "cree":
                brouillon = self.boite.creer_brouillon(demande["message_id"], texte)
                self.boite.envoyer_brouillon(brouillon["draft_id"])
                conv.messages_traites.append(demande["message_id"])
                self.etat.enregistrer(conv, "visite_confirmee", "visite creee et confirmation envoyee",
                                      event_id=visite["event_id"])
                bilan.decision = "visite_creee"
                return bilan
        # creneau pris entre-temps (ou devenu impossible) : hors du bloc, le nouvel email
        # sera de nouveau soumis au conseiller
        return self._proposer_autres(demande, conv, bilan, fiche, creneau, visite)

    def _proposer_autres(self, demande: dict, conv: Conversation, bilan: Bilan, fiche: dict,
                         creneau: datetime, visite: dict) -> Bilan:
        alternatives = [datetime.fromisoformat(c) for c in visite.get("alternatives", [])][:3]
        if not alternatives:
            jour = creneau.replace(hour=0, minute=0)
            alternatives = self.agenda.lister_creneaux_libres(fiche["conseiller"], jour,
                                                              jour + timedelta(days=3))
        brouillon = self.boite.creer_brouillon(demande["message_id"],
                                               texte_alternatives(fiche, alternatives, demande["client_nom"]))
        self.etat.enregistrer(conv, "brouillon_en_attente", f"creneau indisponible : {visite['statut']}",
                              draft_id=brouillon["draft_id"], creneaux=[c.isoformat() for c in alternatives])
        bilan.creneaux = conv.creneaux
        self._envoyer(demande, conv, bilan, brouillon["draft_id"],
                      "creneaux_proposes" if alternatives else "transmis")
        if bilan.decision == "envoye":
            bilan.decision = "creneau_pris"
            if not alternatives:
                self.boite.transmettre_conseiller(demande["message_id"], "plus de creneau libre")
        return bilan

    def _visite_du_client(self, fiche: dict, visite: dict, demande: dict) -> bool:
        cal_id = self.agenda.agendas[fiche["conseiller"]]
        existant = self.agenda.service.events().get(calendarId=cal_id, eventId=visite["event_id"]).execute()
        prive = existant.get("extendedProperties", {}).get("private", {})
        return prive.get("client_email") == demande["client_email"] and prive.get("bien_id") == fiche["id"]

    # --- sortie de route : erreur technique ------------------------------------------------
    def _erreur(self, demande: dict, conv: Conversation, exc: Exception) -> Bilan:
        """Le message reste "a traiter" et sera repris au prochain passage ; apres
        MAX_TENTATIVES echecs, il est confie a un conseiller. L'etat de la conversation est garde."""
        trace = Trace(self.config.dossier_traces, "erreur")
        trace.ecrire({"type": "demande", "texte": f"{demande['objet']} ({demande['client_email']})"})
        trace.ecrire({"type": "erreur", "message": f"{type(exc).__name__}: {exc}"})
        bilan = Bilan(demande["message_id"], demande["thread_id"], demande["client_email"],
                      demande["objet"], "suite" if conv.historique else "nouvelle_demande", "erreur",
                      traces=[str(trace.chemin)], detail=f"{type(exc).__name__}: {exc}"[:300])
        conv.tentatives += 1
        if conv.tentatives >= MAX_TENTATIVES:
            try:
                self.boite.transmettre_conseiller(demande["message_id"], "erreurs techniques repetees")
            except Exception:  # Gmail lui-meme indisponible : on reessaiera au prochain passage
                self.etat.enregistrer(conv, conv.etat or "erreur", f"erreur : {bilan.detail}")
                return bilan
            self.etat.enregistrer(conv, "transmis", f"{conv.tentatives} erreurs : {bilan.detail}")
            bilan.decision = "transmis"
        else:
            self.etat.enregistrer(conv, conv.etat or "erreur", f"erreur, nouvel essai prevu : {bilan.detail}")
        return bilan

    # --- utilitaires ------------------------------------------------------------------
    def _historique(self, demande: dict) -> str:
        precedents = self.boite.historique_fil(demande["thread_id"], sauf=demande["message_id"])
        if not precedents:
            return ""
        lignes = [f"[{m['auteur']}]\n{m['texte']}" for m in precedents]
        return "\nEchanges precedents dans ce fil (du plus ancien au plus recent) :\n" + "\n\n".join(lignes) + "\n"

    @staticmethod
    def _mesurer(bilan: Bilan, resultat: Resultat) -> None:
        bilan.appels_outils += resultat.appels_outils
        bilan.tokens_entree += resultat.tokens_entree
        bilan.tokens_sortie += resultat.tokens_sortie
        bilan.traces.append(resultat.trace)


# --- assemblage ----------------------------------------------------------------------------
OUTILS_AGENDA_MODELE = {"lister_creneaux_libres"}
OUTILS_GMAIL_MODELE = {"creer_brouillon", "transmettre_conseiller"}


def construire_pipeline(
    config: Config,
    service_gmail: Any,
    service_calendar: Any,
    agendas: dict[str, str],
    validation: Validation,
    etat: EtatConversations,
    modele: Any = None,
    modele_interpretation: Any = None,
    maintenant: Callable[[], datetime] | None = None,
) -> Pipeline:
    """Le modele ne voit que les outils de lecture et de brouillon : l'envoi et l'ecriture dans
    l'agenda ne lui sont pas proposes, ils sont declenches par le pipeline apres validation."""
    from agent.agent import construire_agent
    from agent.catalogue_mcp import lecteur_fiches, toolset_catalogue
    from agent.interpretation import agent_interpretation
    from agent.tools.outils_agenda import toolset_agenda
    from agent.tools.outils_gmail import toolset_gmail

    boite = BoiteGmail(service_gmail, validation)
    options = {"maintenant": maintenant} if maintenant else {}
    agenda = Agenda(service_calendar, agendas, validation, **options)
    fiche_bien = lecteur_fiches(config)
    toolsets = [
        toolset_catalogue(config),
        toolset_agenda(agenda, fiche_bien).filtered(lambda ctx, t: t.name in OUTILS_AGENDA_MODELE),
        toolset_gmail(boite).filtered(lambda ctx, t: t.name in OUTILS_GMAIL_MODELE),
    ]
    agent = construire_agent(config, toolsets, modele=modele, avec_agenda=True, avec_gmail=True,
                             maintenant=maintenant)
    return Pipeline(agent, boite, agenda, fiche_bien, etat, config, validation,
                    agent_interpretation(config, modele_interpretation or modele))