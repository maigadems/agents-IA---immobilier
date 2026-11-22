"""Calcul des creneaux de visite libres (fonction pure, sans appel a Google)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from agent.tools.regles import (
    DUREE_VISITE,
    FERMETURE,
    FUSEAU,
    OUVERTURE,
    PAS_CRENEAUX,
    RegleNonRespectee,
    en_dakar,
    verifier_creneau,
)

Plage = tuple[datetime, datetime]


def _chevauche(debut: datetime, fin: datetime, occupes: list[Plage]) -> bool:
    return any(debut < f and o < fin for o, f in occupes)


def _jours(debut: datetime, fin: datetime):
    jour: date = debut.date()
    while jour <= fin.date():
        yield jour
        jour += timedelta(days=1)


def creneaux_libres(
    debut_periode: datetime,
    fin_periode: datetime,
    occupes: list[Plage],
    maintenant: datetime | None = None,
    nombre: int = 3,
    heure_min: time | None = None,
    heure_max: time | None = None,
    ecart: timedelta = timedelta(minutes=30),
) -> list[datetime]:
    """Jusqu'a `nombre` debuts de visite libres, espaces d'au moins `ecart`.

    - periode [debut_periode, fin_periode] ; fenetre quotidienne optionnelle [heure_min, heure_max]
      (ex. "fin d'apres-midi" = 15h-18h) ;
    - respecte les regles de l'agence (verifier_creneau) et les plages `occupes`.
    """
    debut_periode, fin_periode = en_dakar(debut_periode), en_dakar(fin_periode)
    occupes = [(en_dakar(o), en_dakar(f)) for o, f in occupes]
    ouverture = max(OUVERTURE, heure_min or OUVERTURE)
    fermeture = min(FERMETURE, heure_max or FERMETURE)

    trouves: list[datetime] = []
    for jour in _jours(debut_periode, fin_periode):
        t = datetime.combine(jour, ouverture, tzinfo=FUSEAU)
        limite = datetime.combine(jour, fermeture, tzinfo=FUSEAU)
        while t + DUREE_VISITE <= limite and len(trouves) < nombre:
            fin = t + DUREE_VISITE
            if t >= debut_periode and fin <= fin_periode:
                try:
                    verifier_creneau(t, maintenant)
                    libre = not _chevauche(t, fin, occupes)
                except RegleNonRespectee:
                    libre = False
                if libre:
                    trouves.append(t)
                    t += ecart
                    continue
            t += PAS_CRENEAUX
        if len(trouves) >= nombre:
            break
    return trouves
