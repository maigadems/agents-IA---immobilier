"""Les quatre actions d'agenda exposees au modele.

Le modele ne fournit que l'identifiant du bien et des horaires : l'adresse et le conseiller
sont lus dans le catalogue (serveur MCP), jamais recopies par le modele.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Awaitable, Callable

from pydantic_ai import ModelRetry
from pydantic_ai.toolsets import FunctionToolset

from agent.catalogue_mcp import FicheBienErreur
from agent.tools.calendar import Agenda
from agent.tools.regles import DUREE_VISITE, FUSEAU, en_dakar

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
LecteurFiche = Callable[[str], Awaitable[dict]]


def libelle(moment: datetime) -> str:
    moment = en_dakar(moment)
    return f"{JOURS[moment.weekday()]} {moment:%d/%m} a {moment:%H}h{moment:%M}"


def _date(valeur: str, nom: str) -> datetime:
    try:
        if len(valeur) == 10:
            return datetime.combine(date.fromisoformat(valeur), time(0, 0), tzinfo=FUSEAU)
        return en_dakar(datetime.fromisoformat(valeur))
    except ValueError as exc:
        raise ModelRetry(f"{nom} doit etre au format AAAA-MM-JJ ou AAAA-MM-JJTHH:MM (recu {valeur!r}).") from exc


def _heure(valeur: str | None, nom: str) -> time | None:
    if not valeur:
        return None
    try:
        return time.fromisoformat(valeur)
    except ValueError as exc:
        raise ModelRetry(f"{nom} doit etre au format HH:MM (recu {valeur!r}).") from exc


def toolset_agenda(agenda: Agenda, fiche_bien: LecteurFiche) -> FunctionToolset:
    outils = FunctionToolset(id="agenda")

    async def _fiche(bien_id: str) -> dict:
        try:
            return await fiche_bien(bien_id)
        except FicheBienErreur as exc:
            raise ModelRetry(str(exc)) from exc

    @outils.tool_plain
    async def lister_creneaux_libres(
        bien_id: str,
        date_debut: str,
        date_fin: str,
        heure_min: str | None = None,
        heure_max: str | None = None,
    ) -> dict:
        """Creneaux de visite REELLEMENT libres dans l'agenda du conseiller qui gere le bien.

        Args:
            bien_id: identifiant du bien a visiter, ex. "SK-001".
            date_debut: debut de la periode, "AAAA-MM-JJ" (ex. jeudi prochain).
            date_fin: fin de la periode incluse, "AAAA-MM-JJ" (egale a date_debut pour un seul jour).
            heure_min: heure de debut au plus tot "HH:MM" (fin d'apres-midi = "15:00").
            heure_max: heure de fin au plus tard "HH:MM" (fin d'apres-midi = "18:00").

        Renvoie au plus 3 creneaux de 45 min. Ne propose JAMAIS d'autre horaire que ceux-ci.
        """
        fiche = await _fiche(bien_id)
        debut = _date(date_debut, "date_debut")
        fin = _date(date_fin, "date_fin")
        if len(date_fin) == 10:
            fin = fin + timedelta(days=1) - timedelta(minutes=1)
        creneaux = agenda.lister_creneaux_libres(
            fiche["conseiller"], debut, fin, _heure(heure_min, "heure_min"), _heure(heure_max, "heure_max"))
        return {
            "bien_id": fiche["id"],
            "conseiller": fiche["conseiller"],
            "creneaux": [{"debut": c.isoformat(), "fin": (c + DUREE_VISITE).isoformat(),
                          "libelle": libelle(c)} for c in creneaux],
            "message": "" if creneaux else "Aucun creneau libre sur cette periode : proposer une autre date.",
        }

    @outils.tool_plain
    async def creer_visite(bien_id: str, debut: str, client_nom: str, client_email: str) -> dict:
        """Inscrit une visite dans l'agenda, APRES validation d'un conseiller.

        A n'appeler que lorsque le client a CONFIRME un creneau renvoye par lister_creneaux_libres.

        Args:
            bien_id: identifiant du bien, ex. "SK-001".
            debut: debut exact du creneau confirme, "AAAA-MM-JJTHH:MM".
            client_nom: nom du client.
            client_email: adresse email du client.
        """
        fiche = await _fiche(bien_id)
        return agenda.creer_visite(fiche, _date(debut, "debut"), client_nom, client_email)

    @outils.tool_plain
    async def deplacer_visite(bien_id: str, event_id: str, nouveau_debut: str) -> dict:
        """Deplace une visite existante, APRES validation d'un conseiller.

        Args:
            bien_id: identifiant du bien de la visite.
            event_id: identifiant de l'evenement renvoye par creer_visite.
            nouveau_debut: nouveau debut, "AAAA-MM-JJTHH:MM".
        """
        fiche = await _fiche(bien_id)
        return agenda.deplacer_visite(fiche["conseiller"], event_id, _date(nouveau_debut, "nouveau_debut"))

    @outils.tool_plain
    async def annuler_visite(bien_id: str, event_id: str) -> dict:
        """Annule une visite existante, APRES validation d'un conseiller.

        Args:
            bien_id: identifiant du bien de la visite.
            event_id: identifiant de l'evenement renvoye par creer_visite.
        """
        fiche = await _fiche(bien_id)
        return agenda.annuler_visite(fiche["conseiller"], event_id)

    return outils
