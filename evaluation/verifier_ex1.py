"""Critere d'acceptation de l'exercice 1 (et 2 : memes resultats via le serveur MCP).

Pour chacune des 10 demandes, l'agent doit :
  - ne citer QUE des identifiants presents dans la base (aucun bien invente) ;
  - citer les biens attendus ;
  - dire clairement qu'aucun bien ne correspond quand la liste attendue est vide.

    python evaluation/verifier_ex1.py            # avec le modele configure dans .env
    python evaluation/verifier_ex1.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from agent.agent import construire_agent, executer  # noqa: E402
from agent.catalogue_mcp import toolset_catalogue  # noqa: E402
from agent.config import Config  # noqa: E402
from mcp_server.catalogue import DB_DEFAUT, creer  # noqa: E402

MOTIF_ID = re.compile(r"\bSK-\d{3}\b", re.IGNORECASE)
MOTS_AUCUN = ("aucun", "pas de bien", "ne correspond", "pas disponible", "aucune")


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


def ids_de_la_base(config_db: Path) -> set[str]:
    if not config_db.exists():
        creer(config_db)
    with sqlite3.connect(config_db) as con:
        return {r[0] for r in con.execute("SELECT id FROM biens")}


def evaluer(reponse: str, attendus: list[str], base: set[str]) -> dict:
    cites = {m.upper() for m in MOTIF_ID.findall(reponse)}
    inventes = sorted(cites - base)
    manquants = sorted(set(attendus) - cites)
    en_trop = sorted(cites - set(attendus))
    annonce_aucun = any(m in _sans_accents(reponse) for m in MOTS_AUCUN)
    if attendus:
        ok = not inventes and not manquants
    else:
        ok = not cites and annonce_aucun
    return {"ok": ok, "cites": sorted(cites), "inventes": inventes,
            "manquants": manquants, "en_trop": en_trop, "annonce_aucun": annonce_aucun}


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="ecrit le detail des resultats")
    args = parser.parse_args()

    db = Path(os.getenv("CATALOGUE_DB_PATH", DB_DEFAUT))
    db = db if db.is_absolute() else RACINE / db
    base = ids_de_la_base(db)

    demandes = json.loads((RACINE / "evaluation" / "demandes_ex1.json").read_text(encoding="utf-8"))
    config = Config()
    agent = construire_agent(config, [toolset_catalogue(config)])

    lignes, reussites = [], 0
    for d in demandes:
        r = executer(agent, d["demande"], config, libelle=f"ex1-{d['id']}")
        verdict = evaluer(r.texte, d["attendus"], base)
        reussites += verdict["ok"]
        lignes.append({**d, **verdict, "reponse": r.texte, "trace": r.trace,
                       "appels_outils": r.appels_outils, "duree_s": round(r.duree_s, 2)})
        etat = "OK " if verdict["ok"] else "KO "
        print(f"{etat} {d['id']}  attendus={d['attendus'] or 'aucun'}  cites={verdict['cites'] or 'aucun'}"
              + (f"  INVENTES={verdict['inventes']}" if verdict["inventes"] else ""))

    total_inventes = sum(len(l["inventes"]) for l in lignes)
    print(f"\n{reussites}/{len(demandes)} demandes correctes, {total_inventes} bien(s) invente(s).")
    if args.json:
        args.json.write_text(json.dumps(lignes, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if reussites == len(demandes) else 1


if __name__ == "__main__":
    sys.exit(main())
