"""Point d'entree en ligne de commande.

    python -m agent.main demande "un F3 a Mermoz a moins de 400 000 F"
    python -m agent.main trace traces/<fichier>.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent.agent import construire_agent, executer
from agent.catalogue_mcp import toolset_catalogue
from agent.config import Config
from agent.traces import resume_lisible


def _console_utf8() -> None:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")


def cmd_demande(args: argparse.Namespace) -> int:
    config = Config()
    agent = construire_agent(config, [toolset_catalogue(config)])
    resultat = executer(agent, args.texte, config)
    print(resultat.texte)
    print(f"\n--- {resultat.appels_outils} appel(s) d'outils, "
          f"{resultat.tokens_entree + resultat.tokens_sortie} tokens, "
          f"{resultat.duree_s:.1f} s")
    print(f"--- trace : {resultat.trace}")
    if args.verbeux:
        print("\n" + resume_lisible(Path(resultat.trace)))
    return 0 if resultat.erreur is None else 1


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
    p.set_defaults(func=cmd_demande)

    p = sous.add_parser("trace", help="affiche une trace de facon lisible")
    p.add_argument("fichier")
    p.set_defaults(func=cmd_trace)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
