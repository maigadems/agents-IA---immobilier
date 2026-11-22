from datetime import datetime

import pytest

from agent.tools.regles import FUSEAU, RegleNonRespectee, verifier_creneau

MAINTENANT = datetime(2026, 11, 23, 8, 0, tzinfo=FUSEAU)  # lundi 23/11/2026


def test_creneau_valide():
    debut = verifier_creneau(datetime(2026, 11, 26, 16, 0), MAINTENANT)  # jeudi 16h
    assert debut.tzinfo == FUSEAU


@pytest.mark.parametrize("debut, motif", [
    (datetime(2026, 11, 29, 10, 0), "dimanche"),
    (datetime(2026, 11, 26, 8, 30), "9h"),
    (datetime(2026, 11, 26, 17, 30), "9h"),  # finirait a 18h15
    (datetime(2026, 11, 23, 9, 0), "trop proche"),
])
def test_creneaux_refuses(debut, motif):
    with pytest.raises(RegleNonRespectee, match=motif):
        verifier_creneau(debut, MAINTENANT)


def test_derniere_visite_17h15_acceptee():
    verifier_creneau(datetime(2026, 11, 28, 17, 15), MAINTENANT)  # samedi


def test_heure_utc_convertie_en_dakar():
    # Dakar = UTC+0 toute l'annee : 16h UTC = 16h a Dakar
    from datetime import timezone
    debut = verifier_creneau(datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc), MAINTENANT)
    assert debut.hour == 16
