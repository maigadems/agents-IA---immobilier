"""Ex 6 : rejoue les 15 emails de test et mesure ce que l'agent traite correctement.

    python evaluation/evaluer_ex6.py                 # AVANT puis APRES correction (tableau comparatif)
    python evaluation/evaluer_ex6.py --seul apres    # une seule version
    python evaluation/evaluer_ex6.py --emails T01,T07

Le vrai modele (configure dans .env) et le vrai serveur MCP sont utilises. Gmail et Calendar
sont simules en memoire (evaluation/simulateurs.py) : chaque rejeu part du meme etat, sans
toucher au compte de test. La date est fixee (lundi 23/11/2026 08:00) et les agendas sont
pre-remplis : les resultats sont reproductibles. Le conseiller simule valide chaque envoi,
on mesure donc les decisions de l'agent et non celles du conseiller.

Sorties : evaluation/resultats/ex6_<version>.md et .json, et ex6_avant_apres.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from agent.config import Config  # noqa: E402
from agent.etat import EtatConversations  # noqa: E402
from agent.pipeline import construire_pipeline  # noqa: E402
from agent.tools.regles import en_dakar  # noqa: E402
from agent.tools.validation import Validation, toujours  # noqa: E402
from evaluation.criteres_ex6 import evaluer  # noqa: E402
from evaluation.simulateurs import FauxCalendar, FauxGmail  # noqa: E402
from mcp_server.catalogue import DB_DEFAUT, creer  # noqa: E402

JEU = RACINE / "evaluation" / "emails" / "ex6_emails.json"
RESULTATS = RACINE / "evaluation" / "resultats"
AGENDAS = {"Awa Diop": "awa@cal", "Moussa Ndiaye": "moussa@cal", "Fatou Sow": "fatou@cal"}
VERSIONS = {"avant": "aucun", "apres": "tous"}     # valeur de CORRECTIFS pour chaque version


def ids_catalogue() -> set[str]:
    db = Path(os.getenv("CATALOGUE_DB_PATH", DB_DEFAUT))
    db = db if db.is_absolute() else RACINE / db
    if not db.exists():
        creer(db)
    with sqlite3.connect(db) as con:
        return {r[0] for r in con.execute("SELECT id FROM biens")}


def _date(valeur: str) -> datetime:
    return en_dakar(datetime.fromisoformat(valeur))


def rejouer(jeu: dict, modele=None, modele_interpretation=None, emails: set[str] | None = None) -> list[dict]:
    """Traite chaque email du jeu dans un monde simule neuf ; renvoie une ligne par email."""
    maintenant = _date(jeu["maintenant"])
    occupe = {c: [(_date(d), _date(f)) for d, f in plages] for c, plages in jeu["agenda_occupe"].items()}
    base = ids_catalogue()
    lignes = []
    for email in jeu["emails"]:
        if emails and email["id"] not in emails:
            continue
        gmail, cal = FauxGmail(), FauxCalendar()
        for conseiller, plages in occupe.items():
            for i, (d, f) in enumerate(plages):
                cal.insert(AGENDAS[conseiller], {"id": f"occupe{i}", "summary": "Deja reserve",
                                                 "start": {"dateTime": d.isoformat()},
                                                 "end": {"dateTime": f.isoformat()}}).execute()
        pipeline = construire_pipeline(Config(), gmail, cal, AGENDAS, Validation(toujours(True)),
                                       EtatConversations(), modele=modele,
                                       modele_interpretation=modele_interpretation,
                                       maintenant=lambda: maintenant)
        gmail.recevoir(email["de"], email["objet"], email["corps"])
        bilans = pipeline.passe(1)
        bilan = bilans[0] if bilans else None
        decision = bilan.decision if bilan else "aucune"
        verdict = evaluer(email["attendu"], decision, bilan.biens if bilan else [],
                          bilan.creneaux if bilan else [], bilan.reponse if bilan else "", base,
                          occupe.get(bilan.conseiller, []) if bilan else [], maintenant)
        lignes.append({
            "id": email["id"], "categorie": email["categorie"], "attendu": email["attendu"]["decision"],
            "decision": decision, **verdict,
            "biens": bilan.biens if bilan else [], "creneaux": bilan.creneaux if bilan else [],
            "appels_outils": bilan.appels_outils if bilan else 0,
            "tokens": (bilan.tokens_entree + bilan.tokens_sortie) if bilan else 0,
            "duree_s": round(bilan.duree_s, 2) if bilan else 0.0,
            "traces": bilan.traces if bilan else [], "detail": bilan.detail if bilan else "",
            "bilan": asdict(bilan) if bilan else None,
        })
    return lignes


def synthese(lignes: list[dict]) -> dict:
    n = len(lignes) or 1
    return {
        "emails": len(lignes),
        "reussis": sum(l["ok"] for l in lignes),
        "taux_reussite": round(100 * sum(l["ok"] for l in lignes) / n, 1),
        "appels_outils_moyen": round(sum(l["appels_outils"] for l in lignes) / n, 2),
        "tokens_moyen": round(sum(l["tokens"] for l in lignes) / n),
        "tokens_total": sum(l["tokens"] for l in lignes),
        "duree_moyenne_s": round(sum(l["duree_s"] for l in lignes) / n, 2),
    }


def tableau(lignes: list[dict], titre: str) -> str:
    s = synthese(lignes)
    md = [f"## {titre}", "",
          f"**{s['reussis']}/{s['emails']} emails reussis ({s['taux_reussite']} %)** · "
          f"{s['appels_outils_moyen']} appels d'outils, {s['tokens_moyen']} tokens et "
          f"{s['duree_moyenne_s']} s par email en moyenne ({s['tokens_total']} tokens au total).", "",
          "| Email | Categorie | Attendu | Obtenu | Biens | Creneaux | Appels | Tokens | Duree (s) | Resultat |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for l in lignes:
        resultat = "OK" if l["ok"] else "ECHEC : " + " ; ".join(l["problemes"])[:160]
        md.append(f"| {l['id']} | {l['categorie']} | {l['attendu']} | {l['decision']} | "
                  f"{', '.join(l['biens']) or '-'} | {len(l['creneaux'])} | {l['appels_outils']} | "
                  f"{l['tokens']} | {l['duree_s']} | {resultat} |")
    return "\n".join(md) + "\n"


def comparaison(resultats: dict[str, list[dict]]) -> str:
    avant, apres = resultats["avant"], resultats["apres"]
    sa, sp = synthese(avant), synthese(apres)
    md = ["## Avant / apres correction", "",
          "| Indicateur | Avant | Apres |", "|---|---|---|",
          f"| Emails reussis | {sa['reussis']}/{sa['emails']} ({sa['taux_reussite']} %) | "
          f"{sp['reussis']}/{sp['emails']} ({sp['taux_reussite']} %) |",
          f"| Appels d'outils par email | {sa['appels_outils_moyen']} | {sp['appels_outils_moyen']} |",
          f"| Tokens par email | {sa['tokens_moyen']} | {sp['tokens_moyen']} |",
          f"| Duree par email (s) | {sa['duree_moyenne_s']} | {sp['duree_moyenne_s']} |", "",
          "| Email | Avant | Apres |", "|---|---|---|"]
    par_id = {l["id"]: l for l in apres}
    for l in avant:
        p = par_id.get(l["id"])
        md.append(f"| {l['id']} ({l['categorie']}) | {'OK' if l['ok'] else 'echec'} | "
                  f"{'OK' if p and p['ok'] else 'echec'} |")
    return "\n".join(md) + "\n"


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluation de l'agent sur les 15 emails (ex 6)")
    parser.add_argument("--seul", choices=sorted(VERSIONS), help="ne rejouer qu'une version")
    parser.add_argument("--emails", help="identifiants separes par des virgules (ex. T01,T07)")
    args = parser.parse_args()

    from pydantic_ai.exceptions import ModelConnectionError

    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    choix = set(args.emails.split(",")) if args.emails else None
    RESULTATS.mkdir(parents=True, exist_ok=True)
    resultats = {}
    for version in ([args.seul] if args.seul else ["avant", "apres"]):
        os.environ["CORRECTIFS"] = VERSIONS[version]
        print(f"\n=== Version {version} (CORRECTIFS={VERSIONS[version]}) ===")
        try:
            lignes = rejouer(jeu, emails=choix)
        except ModelConnectionError:
            print("Modele injoignable : lancez Ollama ou renseignez une API dans .env.", file=sys.stderr)
            return 2
        resultats[version] = lignes
        md = tableau(lignes, f"Resultats {version} correction")
        print(md)
        (RESULTATS / f"ex6_{version}.md").write_text(md, encoding="utf-8")
        (RESULTATS / f"ex6_{version}.json").write_text(
            json.dumps({"synthese": synthese(lignes), "emails": lignes}, ensure_ascii=False, indent=2,
                       default=str), encoding="utf-8")
    if len(resultats) == 2:
        md = comparaison(resultats)
        print(md)
        (RESULTATS / "ex6_avant_apres.md").write_text(md, encoding="utf-8")
    print(f"Resultats ecrits dans {RESULTATS.relative_to(RACINE)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
