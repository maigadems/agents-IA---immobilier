"""Emails ecrits par le code (ex 5) : confirmation de visite et nouveaux creneaux.

Ces messages ne contiennent que des donnees verifiees (fiche du catalogue, creneau de
l'agenda) : le modele n'intervient pas, il ne peut donc rien y inventer. La signature de
l'agence est ajoutee par BoiteGmail.
"""

from __future__ import annotations

from datetime import datetime

from agent.tools.outils_agenda import libelle


def _salutation(client_nom: str) -> str:
    nom = (client_nom or "").strip()
    return f"Bonjour {nom}," if nom and "@" not in nom else "Bonjour,"


def _bien(fiche: dict) -> str:
    return f"{fiche['id']} ({fiche.get('type_bien', 'bien')}, {fiche.get('quartier', '')})"


def texte_confirmation(fiche: dict, debut: datetime, client_nom: str) -> str:
    return (
        f"{_salutation(client_nom)}\n\n"
        f"Votre visite du bien {_bien(fiche)} est confirmee pour le {libelle(debut)}.\n\n"
        f"Adresse : {fiche['adresse']}\n"
        f"Conseiller : {fiche['conseiller']}\n"
        f"Duree : 45 minutes\n\n"
        "Si vous avez un empechement, repondez simplement a cet email et nous conviendrons "
        "d'un autre horaire."
    )


def texte_alternatives(fiche: dict, creneaux: list[datetime], client_nom: str) -> str:
    entete = (f"{_salutation(client_nom)}\n\n"
              f"Le creneau que vous aviez choisi pour visiter le bien {_bien(fiche)} "
              "vient malheureusement d'etre reserve.\n\n")
    if not creneaux:
        return entete + ("Nous n'avons pas d'autre creneau libre dans les prochains jours : un "
                         "conseiller vous recontactera tres vite pour fixer une date.")
    lignes = "\n".join(f"- {libelle(c)}" for c in creneaux)
    return entete + (f"Voici d'autres creneaux disponibles :\n{lignes}\n\n"
                     "Repondez a cet email en indiquant celui qui vous convient.")
