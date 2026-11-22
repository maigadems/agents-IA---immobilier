"""Emails ecrits par le code : uniquement des donnees du catalogue et de l'agenda."""

from datetime import datetime

from agent.courriers import texte_alternatives, texte_confirmation
from agent.tools.regles import FUSEAU

FICHE = {"id": "SK-009", "type_bien": "villa", "quartier": "Almadies",
         "adresse": "Route des Almadies, Almadies", "conseiller": "Fatou Sow"}
JEUDI = datetime(2026, 11, 26, 16, 45, tzinfo=FUSEAU)


def test_confirmation_contient_adresse_conseiller_et_horaire():
    texte = texte_confirmation(FICHE, JEUDI, "Claire Mendy")
    assert texte.startswith("Bonjour Claire Mendy,")
    assert "jeudi 26/11 a 16h45" in texte
    assert "Route des Almadies, Almadies" in texte and "Fatou Sow" in texte


def test_salutation_neutre_si_le_nom_est_une_adresse():
    assert texte_confirmation(FICHE, JEUDI, "c@client.sn").startswith("Bonjour,\n")


def test_alternatives_listees():
    texte = texte_alternatives(FICHE, [JEUDI, JEUDI.replace(hour=17)], "Claire")
    assert "- jeudi 26/11 a 16h45" in texte and "- jeudi 26/11 a 17h45" in texte


def test_sans_alternative_un_conseiller_recontacte():
    assert "conseiller vous recontactera" in texte_alternatives(FICHE, [], "Claire")
