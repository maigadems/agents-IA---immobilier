"""Criteres de l'exercice 3 avec un faux Google Calendar."""

from datetime import datetime, time

import pytest

from agent.tools.calendar import Agenda
from agent.tools.regles import FUSEAU
from agent.tools.validation import Validation, toujours
from faux_google import FauxCalendar

MAINTENANT = datetime(2026, 11, 23, 8, 0, tzinfo=FUSEAU)  # lundi 23/11
AGENDAS = {"Awa Diop": "awa@cal", "Moussa Ndiaye": "moussa@cal", "Fatou Sow": "fatou@cal"}
FICHE = {"id": "SK-001", "type_bien": "appartement", "quartier": "Mermoz",
         "adresse": "Rue MZ 12, Mermoz Pyrotechnie", "conseiller": "Awa Diop"}


def d(jour, h, m=0):
    return datetime(2026, 11, jour, h, m, tzinfo=FUSEAU)


@pytest.fixture
def faux():
    return FauxCalendar()


def agenda(faux, accord=True):
    return Agenda(faux, AGENDAS, Validation(toujours(accord)), maintenant=lambda: MAINTENANT)


def test_jeudi_prochain_fin_d_apres_midi_trois_creneaux_libres(faux):
    a = agenda(faux)
    a.creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    libres = a.lister_creneaux_libres("Awa Diop", d(26, 0), d(26, 23, 59), time(15), time(18))
    assert len(libres) == 3
    assert d(26, 16) not in libres and all(not (d(26, 15, 15) < c < d(26, 16, 45)) for c in libres)


def test_evenement_valide_avec_bon_conseiller_et_adresse(faux):
    r = agenda(faux).creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    assert r["statut"] == "cree"
    [ev] = faux.actifs("awa@cal")
    assert ev["location"] == FICHE["adresse"]
    assert ev["start"]["dateTime"].startswith("2026-11-26T16:00")
    assert ev["end"]["dateTime"].startswith("2026-11-26T16:45")
    assert ev["start"]["timeZone"] == "Africa/Dakar"
    assert faux.actifs("moussa@cal") == []


def test_deux_demandes_sur_le_meme_creneau_aucun_doublon(faux):
    a = agenda(faux)
    r1 = a.creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    r2 = a.creer_visite(FICHE, d(26, 16), "Client B", "b@test.sn")
    assert r1["statut"] == "cree" and r2["statut"] == "creneau_pris"
    assert r2["alternatives"]
    assert len(faux.actifs("awa@cal")) == 1


def test_course_entre_deux_demandes_bloquee_par_id_deterministe(faux, monkeypatch):
    a = agenda(faux)
    a.creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    # simule une 2e demande qui a verifie la disponibilite AVANT la 1re ecriture
    monkeypatch.setattr(a, "_est_libre", lambda *args, **kw: True)
    r = a.creer_visite(FICHE, d(26, 16), "Client B", "b@test.sn")
    assert r["statut"] == "doublon" and len(faux.actifs("awa@cal")) == 1


def test_refus_du_conseiller_rien_n_est_ecrit(faux):
    r = agenda(faux, accord=False).creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    assert r["statut"] == "refuse_par_conseiller" and faux.inserts == 0


def test_regle_non_respectee_pas_de_validation_demandee(faux):
    a = agenda(faux)
    r = a.creer_visite(FICHE, d(29, 10), "Client A", "a@test.sn")  # dimanche
    assert r["statut"] == "regle_non_respectee" and a.validation.journal == []


def test_deplacer_puis_annuler(faux):
    a = agenda(faux)
    cree = a.creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    dep = a.deplacer_visite("Awa Diop", cree["event_id"], d(27, 10))
    assert dep["statut"] == "deplace"
    assert faux.actifs("awa@cal")[0]["start"]["dateTime"].startswith("2026-11-27T10:00")
    ann = a.annuler_visite("Awa Diop", cree["event_id"])
    assert ann["statut"] == "annule" and faux.actifs("awa@cal") == []
    assert [j["action"] for j in a.validation.journal] == [
        "Creer une visite dans l'agenda", "Deplacer une visite", "Annuler une visite"]


def test_creneau_d_une_visite_annulee_peut_etre_repris(faux):
    a = agenda(faux)
    cree = a.creer_visite(FICHE, d(26, 16), "Client A", "a@test.sn")
    a.annuler_visite("Awa Diop", cree["event_id"])
    r = a.creer_visite(FICHE, d(26, 16), "Client B", "b@test.sn")
    assert r["statut"] == "cree" and "Client B" in faux.actifs("awa@cal")[0]["summary"]
