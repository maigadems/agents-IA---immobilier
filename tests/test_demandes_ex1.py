"""Les resultats attendus des 10 demandes restent coherents avec le catalogue."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client

from mcp_server.mcp_server import creer_serveur

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "evaluation"))
from verifier_ex1 import evaluer  # noqa: E402

DEMANDES = json.loads((RACINE / "evaluation" / "demandes_ex1.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("d", DEMANDES, ids=[d["id"] for d in DEMANDES])
def test_attendus_conformes_au_serveur(d):
    async def _run():
        async with Client(creer_serveur()) as c:
            return await c.call_tool("rechercher_biens", {**d["filtres"], "limite": 10})
    r = asyncio.run(_run())
    assert sorted(b["id"] for b in r.data["biens"]) == sorted(d["attendus"])


def test_evaluer_detecte_un_bien_invente():
    v = evaluer("Je vous propose SK-001 et SK-777.", ["SK-001"], {"SK-001"})
    assert not v["ok"] and v["inventes"] == ["SK-777"]


def test_evaluer_exige_d_annoncer_aucun_resultat():
    assert evaluer("Aucun bien ne correspond a votre demande.", [], {"SK-001"})["ok"]
    assert not evaluer("Voici nos offres.", [], {"SK-001"})["ok"]
