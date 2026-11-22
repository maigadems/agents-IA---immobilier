"""Le serveur MCP teste comme le ferait n'importe quel client MCP (en memoire)."""

import asyncio
import json

import pytest
from fastmcp import Client

from mcp_server.mcp_server import creer_serveur


def appeler(outil: str, args: dict | None = None):
    async def _run():
        async with Client(creer_serveur()) as c:
            return await c.call_tool(outil, args or {}, raise_on_error=False)
    return asyncio.run(_run())


def test_outils_et_ressource_exposes():
    async def _run():
        async with Client(creer_serveur()) as c:
            outils = {t.name for t in await c.list_tools()}
            ressources = {str(r.uri) for r in await c.list_resources()}
            return outils, ressources
    outils, ressources = asyncio.run(_run())
    assert {"rechercher_biens", "detail_bien"} <= outils
    assert "agence://infos" in ressources


def test_f3_mermoz_moins_de_400000():
    r = appeler("rechercher_biens", {"quartier": "mermoz", "pieces_min": 3,
                                     "pieces_max": 3, "loyer_max_fcfa": 400000})
    assert [b["id"] for b in r.data["biens"]] == ["SK-001"]


def test_aucun_resultat_est_explicite():
    r = appeler("rechercher_biens", {"quartier": "Hann", "type_bien": "villa"})
    assert r.data["nombre"] == 0 and r.data["biens"] == []
    assert "Aucun bien" in r.data["message"]


def test_biens_loues_exclus_par_defaut():
    r = appeler("rechercher_biens", {"quartier": "Mermoz", "limite": 10})
    assert all(b["disponibilite"] == "disponible" for b in r.data["biens"])


def test_detail_bien_contient_adresse():
    r = appeler("detail_bien", {"bien_id": "sk-001"})
    assert r.data["id"] == "SK-001" and "Mermoz" in r.data["adresse"]


@pytest.mark.parametrize("args", [
    {"limite": 50},
    {"pieces_min": 4, "pieces_max": 2},
    {"loyer_min_fcfa": 500000, "loyer_max_fcfa": 100000},
])
def test_arguments_invalides_renvoient_une_erreur_lisible(args):
    r = appeler("rechercher_biens", args)
    assert r.is_error


def test_detail_bien_inconnu():
    r = appeler("detail_bien", {"bien_id": "SK-999"})
    assert r.is_error and "SK-999" in r.content[0].text


def test_ressource_agence():
    async def _run():
        async with Client(creer_serveur()) as c:
            return await c.read_resource("agence://infos")
    infos = json.loads(asyncio.run(_run())[0].text)
    assert "horaires_visite" in infos and "zones_couvertes" in infos
