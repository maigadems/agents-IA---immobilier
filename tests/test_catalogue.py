import sqlite3

from mcp_server.catalogue import BIENS, CONSEILLERS, creer, norme


def test_trente_biens(tmp_path):
    db = creer(tmp_path / "c.db")
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM biens").fetchone()[0] == 30
    assert len(BIENS) == 30


def test_champs_obligatoires(tmp_path):
    con = sqlite3.connect(creer(tmp_path / "c.db"))
    con.row_factory = sqlite3.Row
    for r in con.execute("SELECT * FROM biens"):
        assert r["type_bien"] and r["quartier"] and r["adresse"]
        assert r["loyer_fcfa"] > 0 and r["pieces"] >= 1
        assert r["disponibilite"] in {"disponible", "reserve", "loue"}


def test_chaque_conseiller_a_des_biens(tmp_path):
    con = sqlite3.connect(creer(tmp_path / "c.db"))
    conseillers = {r[0] for r in con.execute("SELECT DISTINCT conseiller FROM biens")}
    assert conseillers == set(CONSEILLERS)


def test_identifiants_sk(tmp_path):
    con = sqlite3.connect(creer(tmp_path / "c.db"))
    ids = [r[0] for r in con.execute("SELECT id FROM biens ORDER BY id")]
    assert ids[0] == "SK-001" and ids[-1] == "SK-030"


def test_norme_ignore_accents_et_tirets():
    assert norme("Sacré-Cœur") == norme("sacre coeur") or norme("Sacré-Coeur") == "sacre coeur"
    assert norme("  MERMOZ ") == "mermoz"
