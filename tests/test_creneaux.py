from datetime import datetime, time, timedelta

from agent.tools.creneaux import creneaux_libres
from agent.tools.regles import DUREE_VISITE, FUSEAU

MAINTENANT = datetime(2026, 11, 23, 8, 0, tzinfo=FUSEAU)   # lundi
JEUDI = (datetime(2026, 11, 26, 0, 0), datetime(2026, 11, 26, 23, 59))


def d(jour, h, m=0):
    return datetime(2026, 11, jour, h, m, tzinfo=FUSEAU)


def test_jeudi_fin_d_apres_midi_trois_creneaux_reellement_libres():
    occupes = [(d(26, 16), d(26, 16, 45))]
    r = creneaux_libres(*JEUDI, occupes, MAINTENANT, heure_min=time(15, 0), heure_max=time(18, 0))
    assert [c.strftime("%H:%M") for c in r] == ["15:00", "16:45", "17:15"]
    for c in r:  # aucun ne chevauche la visite deja prevue
        assert c + DUREE_VISITE <= d(26, 16) or c >= d(26, 16, 45)


def test_propositions_espacees_de_30_minutes():
    r = creneaux_libres(*JEUDI, [], MAINTENANT)
    assert [c.strftime("%H:%M") for c in r] == ["09:00", "09:30", "10:00"]
    assert all(b - a >= timedelta(minutes=30) for a, b in zip(r, r[1:]))


def test_journee_pleine_passe_au_jour_suivant():
    occupes = [(d(26, 9), d(26, 18))]
    r = creneaux_libres(d(26, 0), d(28, 23), occupes, MAINTENANT)
    assert r[0] == d(27, 9)


def test_dimanche_exclu():
    assert creneaux_libres(d(29, 0), d(29, 23), [], MAINTENANT) == []


def test_derniere_visite_commence_a_17h15():
    occupes = [(d(26, 9), d(26, 17, 15))]
    assert creneaux_libres(*JEUDI, occupes, MAINTENANT) == [d(26, 17, 15)]
