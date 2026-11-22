"""Reconnaissance du creneau choisi par le client."""

from datetime import datetime

import pytest

from agent.choix_creneau import reconnaitre, sans_citation
from agent.tools.regles import FUSEAU

PROPOSES = [datetime(2026, 11, 26, 15, 0, tzinfo=FUSEAU),     # jeudi 26/11 15h00
            datetime(2026, 11, 26, 16, 45, tzinfo=FUSEAU),    # jeudi 26/11 16h45
            datetime(2026, 11, 28, 10, 0, tzinfo=FUSEAU)]     # samedi 28/11 10h00


@pytest.mark.parametrize("texte, attendu", [
    ("Bonjour, jeudi 16h45 me convient parfaitement.", 1),
    ("Je prends le créneau de 15h.", 0),
    ("Va pour 16:45 alors, merci", 1),
    ("Samedi c'est parfait !", 2),
    ("Le 28/11 svp", 2),
    ("Je choisis le deuxième créneau.", 1),
    ("Le premier créneau me va.", 0),
    ("Option 3 merci", 2),
    ("Waaw, jeudi à 15 heures. Jërëjëf", 0),
])
def test_choix_reconnu(texte, attendu):
    choix = reconnaitre(texte, PROPOSES)
    assert choix.statut == "choisi" and choix.creneau == PROPOSES[attendu]


def test_jeudi_seul_est_ambigu():
    choix = reconnaitre("Jeudi m'arrange.", PROPOSES)
    assert choix.statut == "ambigu" and len(choix.candidats) == 2


def test_heure_non_proposee_est_ambigue():
    assert reconnaitre("Est-ce possible à 11h ?", PROPOSES).statut == "ambigu"


@pytest.mark.parametrize("texte", [
    "Aucun de ces créneaux ne me convient.",
    "Je ne suis pas disponible, avez-vous d'autres dates ?",
    "Finalement j'annule, merci.",
])
def test_refus(texte):
    assert reconnaitre(texte, PROPOSES).statut == "refus"


def test_refus_et_heure_ensemble_reste_ambigu():
    assert reconnaitre("16h45 ne me convient pas", PROPOSES).statut == "ambigu"


def test_sans_indication():
    assert reconnaitre("Merci pour votre réponse rapide.", PROPOSES).statut == "aucun"


def test_message_cite_ignore():
    texte = ("Parfait pour samedi.\n\nLe lun. 23 nov. 2026, Sama Ker a écrit :\n"
             "> jeudi 26/11 a 15h00\n> jeudi 26/11 a 16h45")
    assert "16h45" not in sans_citation(texte)
    assert reconnaitre(texte, PROPOSES).creneau == PROPOSES[2]
