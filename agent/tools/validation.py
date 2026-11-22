"""Validation humaine obligatoire avant toute ecriture (envoi d'email, agenda).

Regle : sans "oui" explicite d'un conseiller, rien n'est ecrit. Par defaut la validation se
fait en ligne de commande ; si aucune console interactive n'est disponible, la reponse est
NON (jamais d'accord implicite).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from agent.traces import Trace

Decideur = Callable[[str, dict], bool]


def decideur_console(action: str, details: dict) -> bool:
    if not sys.stdin or not sys.stdin.isatty():
        print(f"[validation] pas de console interactive : '{action}' REFUSEE par defaut.")
        return False
    print("\n" + "=" * 70)
    print(f"VALIDATION CONSEILLER REQUISE : {action}")
    print("-" * 70)
    for cle, valeur in details.items():
        if isinstance(valeur, str) and "\n" in valeur:
            print(f"{cle} :\n{valeur}")
        else:
            print(f"{cle} : {json.dumps(valeur, ensure_ascii=False) if not isinstance(valeur, str) else valeur}")
    print("=" * 70)
    reponse = input("Valider ? [o/N] ").strip().lower()
    return reponse in {"o", "oui", "y", "yes"}


@dataclass
class Validation:
    """Point de passage unique des ecritures ; garde le journal des decisions."""

    decideur: Decideur = decideur_console
    trace: Trace | None = None
    journal: list[dict] = field(default_factory=list)

    def demander(self, action: str, details: dict) -> bool:
        try:
            accord = bool(self.decideur(action, details))
        except (EOFError, KeyboardInterrupt):
            accord = False
        entree = {"type": "validation", "action": action, "accord": accord,
                  "details": details, "horodatage_decision": datetime.now().isoformat(timespec="seconds")}
        self.journal.append(entree)
        if self.trace:
            self.trace.ecrire(entree)
        return accord


def toujours(reponse: bool) -> Decideur:
    """Decideur automatique, pour les tests uniquement."""
    return lambda action, details: reponse
