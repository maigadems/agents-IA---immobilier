"""Criteres de reussite d'un email de l'evaluation (ex 6).

Un email est reussi si TOUS ses controles passent :
  decision         repondre (reponse envoyee) ou transmettre (conseiller), comme attendu
  biens_inventes   aucun identifiant cite absent du catalogue
  biens_attendus   au moins un des biens attendus est cite (si la liste est donnee)
  biens_aucun      aucun bien cite, quand aucun ne correspond
  biens_interdits  aucun des identifiants interdits (ex. un SK-045 cite par le client)
  creneaux         proposes quand c'est attendu, tous libres dans l'agenda, conformes aux regles
                   de l'agence, dans la periode demandee ; et chaque horaire ecrit dans la
                   reponse fait partie des creneaux renvoyes par l'agenda
"""

from __future__ import annotations

import re
from datetime import date, datetime, time

from agent.tools.regles import DUREE_VISITE, RegleNonRespectee, en_dakar, verifier_creneau

DECISIONS = {"repondre": {"envoye"}, "transmettre": {"transmis", "transmis_automatiquement"}}
JOURS = r"(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)"


def horaires_ecrits(texte: str) -> set[tuple[int, int]]:
    """Horaires cites apres un nom de jour ("jeudi 26/11 a 16h45", "samedi a 10h")."""
    trouves = set()
    for _, h, m in re.findall(JOURS + r"[^\n]{0,25}?\b([01]?\d|2[0-3])\s*[h:]\s*([0-5]\d)?", texte.lower()):
        trouves.add((int(h), int(m or 0)))
    return trouves


def controler_creneaux(creneaux: list[str], attendu: dict, occupations: list[tuple[datetime, datetime]],
                       maintenant: datetime, reponse: str) -> list[str]:
    """Liste des problemes de creneaux (vide = correct)."""
    problemes = []
    debuts = [en_dakar(datetime.fromisoformat(c)) for c in creneaux]
    if attendu.get("creneaux_requis") and not debuts:
        problemes.append("aucun creneau propose")
    periode = attendu.get("periode")
    for d in debuts:
        fin = d + DUREE_VISITE
        if any(o_debut < fin and d < o_fin for o_debut, o_fin in occupations):
            problemes.append(f"{d:%d/%m %H:%M} deja occupe")
        try:
            verifier_creneau(d, maintenant)
        except RegleNonRespectee as exc:
            problemes.append(f"{d:%d/%m %H:%M} : {exc}")
        if periode:
            jour = date.fromisoformat(periode["date"])
            hmin, hmax = time.fromisoformat(periode["heure_min"]), time.fromisoformat(periode["heure_max"])
            if d.date() != jour or d.time() < hmin or fin.time() > hmax:
                problemes.append(f"{d:%d/%m %H:%M} hors de la periode demandee")
    permis = {(d.hour, d.minute) for d in debuts}
    for h, m in sorted(horaires_ecrits(reponse) - permis):
        problemes.append(f"horaire {h}h{m:02d} ecrit dans la reponse sans venir de l'agenda")
    return problemes


def evaluer(attendu: dict, decision: str, biens: list[str], creneaux: list[str], reponse: str,
            base: set[str], occupations: list[tuple[datetime, datetime]], maintenant: datetime) -> dict:
    controles: dict[str, bool] = {"decision": decision in DECISIONS[attendu["decision"]]}
    problemes: list[str] = [] if controles["decision"] else [f"decision {decision}, attendu {attendu['decision']}"]

    inventes = sorted(set(biens) - base)
    controles["biens_inventes"] = not inventes
    if inventes:
        problemes.append(f"biens inventes : {inventes}")
    if attendu.get("biens_un_parmi"):
        controles["biens_attendus"] = bool(set(biens) & set(attendu["biens_un_parmi"]))
        if not controles["biens_attendus"]:
            problemes.append(f"aucun des biens attendus {attendu['biens_un_parmi']} (cites : {biens})")
    if attendu.get("biens_aucun"):
        controles["biens_aucun"] = not biens
        if biens:
            problemes.append(f"biens cites alors qu'aucun ne correspond : {biens}")
    if attendu.get("biens_interdits"):
        interdits = sorted(set(biens) & set(attendu["biens_interdits"]))
        controles["biens_interdits"] = not interdits
        if interdits:
            problemes.append(f"identifiants interdits cites : {interdits}")
    if attendu["decision"] == "repondre":
        soucis = controler_creneaux(creneaux, attendu, occupations, maintenant, reponse)
        controles["creneaux"] = not soucis
        problemes.extend(soucis)
    return {"ok": all(controles.values()), "controles": controles, "problemes": problemes}
