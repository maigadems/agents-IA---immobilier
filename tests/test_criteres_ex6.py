"""Criteres de reussite de l'evaluation (ex 6)."""

from datetime import datetime

from agent.tools.regles import FUSEAU
from evaluation.criteres_ex6 import evaluer, horaires_ecrits

BASE = {f"SK-{i:03d}" for i in range(1, 31)}
LUNDI = datetime(2026, 11, 23, 8, 0, tzinfo=FUSEAU)
JEUDI_FIN = {"decision": "repondre", "biens_un_parmi": ["SK-001"], "creneaux_requis": True,
             "periode": {"date": "2026-11-26", "heure_min": "15:00", "heure_max": "18:00"}}
OCCUPE = [(datetime(2026, 11, 26, 9, tzinfo=FUSEAU), datetime(2026, 11, 26, 12, tzinfo=FUSEAU))]
BON = ["2026-11-26T15:00:00+00:00", "2026-11-26T15:30:00+00:00", "2026-11-26T16:00:00+00:00"]
TEXTE = "SK-001 a Mermoz. Creneaux : jeudi 26/11 a 15h00, jeudi 26/11 a 15h30, jeudi 26/11 a 16h00."


def test_reponse_correcte():
    v = evaluer(JEUDI_FIN, "envoye", ["SK-001"], BON, TEXTE, BASE, OCCUPE, LUNDI)
    assert v["ok"] and v["problemes"] == []


def test_bien_invente():
    v = evaluer(JEUDI_FIN, "envoye", ["SK-001", "SK-045"], BON, TEXTE, BASE, OCCUPE, LUNDI)
    assert not v["ok"] and not v["controles"]["biens_inventes"]


def test_mauvaise_decision():
    v = evaluer({"decision": "transmettre"}, "envoye", [], [], "", BASE, [], LUNDI)
    assert not v["ok"] and v["problemes"] == ["decision envoye, attendu transmettre"]


def test_creneau_occupe_ou_hors_periode():
    attendu = {**JEUDI_FIN, "periode": {"date": "2026-11-26", "heure_min": "09:00", "heure_max": "18:00"}}
    v = evaluer(attendu, "envoye", ["SK-001"], ["2026-11-26T10:00:00+00:00"],
                "jeudi 26/11 a 10h00", BASE, OCCUPE, LUNDI)
    assert any("deja occupe" in p for p in v["problemes"])
    v = evaluer(JEUDI_FIN, "envoye", ["SK-001"], ["2026-11-27T15:00:00+00:00"],
                "vendredi 27/11 a 15h00", BASE, OCCUPE, LUNDI)
    assert any("hors de la periode" in p for p in v["problemes"])


def test_horaire_ecrit_sans_venir_de_l_agenda():
    v = evaluer(JEUDI_FIN, "envoye", ["SK-001"], BON, TEXTE + " Ou bien jeudi a 17h15 ?", BASE, OCCUPE, LUNDI)
    assert not v["controles"]["creneaux"]
    assert any("17h15" in p for p in v["problemes"])


def test_aucun_bien_quand_rien_ne_correspond():
    attendu = {"decision": "repondre", "biens_aucun": True}
    assert evaluer(attendu, "envoye", [], [], "Aucun bien.", BASE, [], LUNDI)["ok"]
    assert not evaluer(attendu, "envoye", ["SK-002"], [], "", BASE, [], LUNDI)["ok"]


def test_horaires_ecrits_ignore_les_horaires_d_ouverture():
    assert horaires_ecrits("Visites de 9h a 18h. Samedi 28/11 a 10h30 ou jeudi a 16h.") == {(10, 30), (16, 0)}
