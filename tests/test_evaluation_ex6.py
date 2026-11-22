"""Le script d'evaluation de l'ex 6, rejoue avec le modele simule (sans vrai modele)."""

import json
from pathlib import Path

from evaluation.evaluer_ex6 import JEU, comparaison, rejouer, synthese, tableau
from modeles_simules import interprete, secretaire

JEU_EX6 = json.loads(Path(JEU).read_text(encoding="utf-8"))


def test_jeu_complet_quinze_emails_toutes_categories():
    categories = {e["categorie"] for e in JEU_EX6["emails"]}
    assert len(JEU_EX6["emails"]) == 15
    assert {"demande simple", "bien inexistant", "creneau deja pris", "demande ambigue", "hors perimetre",
            "tentative d'injection", "francais et wolof"} <= categories


def test_rejeu_et_mesures():
    lignes = rejouer(JEU_EX6, modele=secretaire(), modele_interpretation=interprete(),
                     emails={"T01", "T12", "T13"})
    par_id = {l["id"]: l for l in lignes}
    assert par_id["T01"]["ok"] and par_id["T01"]["biens"] == ["SK-001"]
    assert par_id["T12"]["decision"] == "transmis" and par_id["T12"]["ok"]
    assert par_id["T13"]["decision"] == "transmis_automatiquement" and par_id["T13"]["appels_outils"] == 0
    assert par_id["T01"]["appels_outils"] == 3 and par_id["T01"]["traces"]

    s = synthese(lignes)
    assert s["emails"] == 3 and s["reussis"] == 3 and s["taux_reussite"] == 100.0
    assert "| T01 | demande simple | repondre | envoye | SK-001 | 3 |" in tableau(lignes, "test")
    assert "| T01 (demande simple) | OK | OK |" in comparaison({"avant": lignes, "apres": lignes})


def test_creneau_deja_pris_n_est_jamais_propose():
    # le modele simule demande le jeudi 26/11 : l'agenda d'Awa Diop y est occupe de 9h a 12h
    lignes = rejouer(JEU_EX6, modele=secretaire(heure_min="09:00", heure_max="18:00"),
                     modele_interpretation=interprete(), emails={"T07"})
    [t07] = lignes
    assert t07["ok"], t07["problemes"]
    assert all(c >= "2026-11-26T12:00" for c in t07["creneaux"])
