"""Etat des conversations : persistance par fil Gmail."""

import pytest

from agent.etat import Conversation, EtatConversations


def test_etat_relu_apres_redemarrage(tmp_path):
    chemin = tmp_path / "etat" / "conversations.json"
    etat = EtatConversations(chemin)
    conv = Conversation("t1", "client@test.sn", "Client")
    etat.enregistrer(conv, "creneaux_proposes", "reponse envoyee", bien_id="SK-001",
                     creneaux=["2026-11-26T15:00:00+00:00"])

    relu = EtatConversations(chemin).get("t1")
    assert relu.etat == "creneaux_proposes" and relu.bien_id == "SK-001"
    assert relu.creneaux == ["2026-11-26T15:00:00+00:00"]
    assert relu.historique[-1]["note"] == "reponse envoyee"
    assert not chemin.with_suffix(".tmp").exists()


def test_historique_garde_chaque_etape():
    etat = EtatConversations()
    conv = Conversation("t2", "c@test.sn")
    etat.enregistrer(conv, "brouillon_en_attente")
    etat.enregistrer(conv, "creneaux_proposes")
    etat.enregistrer(conv, "visite_confirmee", event_id="ev1")
    assert [h["etat"] for h in conv.historique] == ["brouillon_en_attente", "creneaux_proposes",
                                                    "visite_confirmee"]
    assert conv.terminee and etat.get("t2").event_id == "ev1"


def test_etat_inconnu_refuse():
    with pytest.raises(ValueError):
        EtatConversations().enregistrer(Conversation("t3", "c@test.sn"), "on_verra")
