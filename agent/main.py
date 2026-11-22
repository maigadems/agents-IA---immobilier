"""Point d'entree en ligne de commande.

    python -m agent.main demande "un F3 a Mermoz a moins de 400 000 F"
    python -m agent.main surveiller          # pipeline complet en continu (ex 5)
    python -m agent.main trace traces/<fichier>.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent.agent import construire_agent, executer
from agent.catalogue_mcp import lecteur_fiches, toolset_catalogue
from agent.config import Config
from agent.tools.validation import Validation
from agent.traces import resume_lisible


def _console_utf8() -> None:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")


def _outils(config: Config, validation: Validation, agenda: bool) -> list:
    toolsets = [toolset_catalogue(config)]
    if agenda:
        from agent.tools.calendar import Agenda
        from agent.tools.google_auth import service_calendar
        from agent.tools.outils_agenda import toolset_agenda
        from agent.tools.regles import agendas_conseillers

        agendas = agendas_conseillers()
        if not agendas:
            raise SystemExit("CALENDAR_ID_CONSEILLER_* absents du .env : lancer scripts/creer_agendas.py")
        toolsets.append(toolset_agenda(Agenda(service_calendar(), agendas, validation),
                                       lecteur_fiches(config)))
    return toolsets


def cmd_demande(args: argparse.Namespace) -> int:
    config = Config()
    validation = Validation()
    agent = construire_agent(config, _outils(config, validation, args.agenda), avec_agenda=args.agenda)
    resultat = executer(agent, args.texte, config, validation=validation)
    print(resultat.texte)
    print(f"\n--- {resultat.appels_outils} appel(s) d'outils, "
          f"{resultat.tokens_entree + resultat.tokens_sortie} tokens, "
          f"{resultat.duree_s:.1f} s")
    print(f"--- trace : {resultat.trace}")
    if args.verbeux:
        print("\n" + resume_lisible(Path(resultat.trace)))
    return 0 if resultat.erreur is None else 1


def cmd_boite(args: argparse.Namespace) -> int:
    from agent.boite import traiter_boite
    from agent.tools.gmail import BoiteGmail
    from agent.tools.google_auth import service_gmail
    from agent.tools.outils_gmail import toolset_gmail

    config = Config()
    validation = Validation()
    boite = BoiteGmail(service_gmail(), validation)
    toolsets = _outils(config, validation, agenda=True) + [toolset_gmail(boite)]
    agent = construire_agent(config, toolsets, avec_agenda=True, avec_gmail=True)
    traitements = traiter_boite(agent, boite, config, validation, args.maximum)
    if not traitements:
        print("Aucune nouvelle demande.")
    for t in traitements:
        print(f"- {t.client_email:30} {t.objet[:40]:40} -> {t.decision}")
        if t.resultat:
            print(f"    trace : {t.resultat.trace}")
    return 0


def _pipeline():
    from agent.etat import EtatConversations
    from agent.pipeline import construire_pipeline
    from agent.tools.google_auth import service_calendar, service_gmail
    from agent.tools.regles import agendas_conseillers

    config = Config()
    agendas = agendas_conseillers()
    if not agendas:
        raise SystemExit("CALENDAR_ID_CONSEILLER_* absents du .env : lancer scripts/creer_agendas.py")
    return config, construire_pipeline(config, service_gmail(), service_calendar(), agendas,
                                       Validation(), EtatConversations(config.fichier_etat))


def _afficher(bilans) -> None:
    for b in bilans:
        print(f"- {b.client_email:30} {b.objet[:35]:35} {b.etape:16} -> {b.decision:24} [{b.etat}]")
        for t in b.traces:
            print(f"    trace : {t}")


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Un passage : chaque nouvel email (ou reponse de client) est traite jusqu'au bout."""
    _, pipeline = _pipeline()
    bilans = pipeline.passe(args.maximum)
    if not bilans:
        print("Aucun nouveau message.")
    _afficher(bilans)
    return 0


def cmd_surveiller(args: argparse.Namespace) -> int:
    """Demo du jury : la boite est relue en continu, le conseiller ne fait que valider."""
    import time

    config, pipeline = _pipeline()
    intervalle = args.intervalle or config.intervalle_s
    print(f"Surveillance de la boite toutes les {intervalle} s (Ctrl+C pour arreter).")
    try:
        while True:
            _afficher(pipeline.passe(args.maximum))
            time.sleep(intervalle)
    except KeyboardInterrupt:
        print("\nArret de la surveillance.")
    return 0


def cmd_conversations(args: argparse.Namespace) -> int:
    from agent.etat import EtatConversations

    conversations = EtatConversations(Config().fichier_etat).toutes()
    if not conversations:
        print("Aucune conversation enregistree.")
    for c in conversations:
        print(f"- {c.client_email:30} {c.etat:22} bien={c.bien_id or '-':7} "
              f"visite={c.event_id or '-'}  ({len(c.historique)} etapes)")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    print(resume_lisible(Path(args.fichier)))
    return 0


def main(argv: list[str] | None = None) -> int:
    _console_utf8()
    parser = argparse.ArgumentParser(prog="agent", description="Agent Sama Ker Immobilier")
    sous = parser.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("demande", help="pose une question a l'agent (catalogue)")
    p.add_argument("texte")
    p.add_argument("-v", "--verbeux", action="store_true", help="affiche la trace")
    p.add_argument("--agenda", action="store_true", help="donne acces a Google Calendar (ex 3)")
    p.set_defaults(func=cmd_demande)

    p = sous.add_parser("boite", help="traite les demandes non lues de Gmail (ex 4)")
    p.add_argument("--maximum", type=int, default=10)
    p.set_defaults(func=cmd_boite)

    p = sous.add_parser("pipeline", help="un passage du pipeline complet (ex 5)")
    p.add_argument("--maximum", type=int, default=10)
    p.set_defaults(func=cmd_pipeline)

    p = sous.add_parser("surveiller", help="pipeline en continu : relit la boite regulierement (ex 5)")
    p.add_argument("--intervalle", type=int, default=None, help="secondes entre deux lectures")
    p.add_argument("--maximum", type=int, default=10)
    p.set_defaults(func=cmd_surveiller)

    p = sous.add_parser("conversations", help="etat de chaque conversation (ex 5)")
    p.set_defaults(func=cmd_conversations)

    p = sous.add_parser("trace", help="affiche une trace de facon lisible")
    p.add_argument("fichier")
    p.set_defaults(func=cmd_trace)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
