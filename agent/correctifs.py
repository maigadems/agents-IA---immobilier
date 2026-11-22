"""Correctifs issus de l'analyse des echecs (ex 6), activables un par un.

Chaque correction apportee apres l'evaluation est enregistree ici, sous un nom. On peut ainsi
rejouer le jeu de test AVANT et APRES correction avec le meme code, en une seule commande
(evaluation/evaluer_ex6.py), et le jury obtient le meme tableau.

Variable d'environnement CORRECTIFS :
  tous  (defaut)     tous les correctifs sont actifs : comportement normal de l'agent
  aucun              comportement d'avant les corrections
  nom1,nom2          seulement ceux-la
"""

from __future__ import annotations

import os

# nom -> description courte (echec constate, correction apportee)
CORRECTIFS: dict[str, str] = {
    "lexique_wolof": (
        "Emails melant francais et wolof (T04, T15) : le besoin exprime en wolof (\"dama soxla\", "
        "\"suba\", \"ci Point E\") risque d'etre mal compris. Correctif : un lexique wolof court "
        "dans le prompt. A confirmer ou remplacer apres analyse des traces du vrai modele."
    ),
}


def actifs() -> set[str]:
    valeur = os.getenv("CORRECTIFS", "tous").strip().lower()
    if valeur in ("", "tous"):
        return set(CORRECTIFS)
    if valeur == "aucun":
        return set()
    demandes = {n.strip() for n in valeur.split(",") if n.strip()}
    inconnus = demandes - set(CORRECTIFS)
    if inconnus:
        raise ValueError(f"Correctif(s) inconnu(s) : {sorted(inconnus)}. Connus : {sorted(CORRECTIFS)}")
    return demandes


def est_actif(nom: str) -> bool:
    return nom in actifs()
