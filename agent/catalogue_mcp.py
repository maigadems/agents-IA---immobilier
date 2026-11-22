"""Connexion au serveur MCP du catalogue (client MCP).

L'agent n'a aucune fonction locale d'acces au catalogue : tout passe par le serveur.
- MCP_SERVER_URL=stdio           -> le serveur mcp_server/mcp_server.py est lance en sous-processus
- MCP_SERVER_URL=http://.../mcp  -> connexion a un serveur deja demarre (HTTP)
"""

from __future__ import annotations

import os
import sys

from fastmcp import Client
from fastmcp.client.transports import ClientTransport, PythonStdioTransport, StreamableHttpTransport
from pydantic_ai.mcp import MCPToolset

from agent.config import RACINE, Config

SCRIPT_SERVEUR = RACINE / "mcp_server" / "mcp_server.py"


def transport_catalogue(config: Config) -> ClientTransport:
    if config.mcp_catalogue == "stdio":
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "FASTMCP_LOG_LEVEL": "WARNING"}
        return PythonStdioTransport(
            SCRIPT_SERVEUR,
            args=["--transport", "stdio"],
            env=env,
            cwd=str(RACINE),
            python_cmd=sys.executable,
        )
    if config.mcp_catalogue.startswith(("http://", "https://")):
        return StreamableHttpTransport(config.mcp_catalogue)
    raise ValueError(f"MCP_SERVER_URL invalide : {config.mcp_catalogue!r} (stdio ou URL http).")


def toolset_catalogue(config: Config) -> MCPToolset:
    """Les outils du catalogue, exposes au modele."""
    return MCPToolset(
        transport_catalogue(config),
        id="catalogue",
        tool_error_behavior="retry",
        max_retries=config.retries_outils,
    )


class FicheBienErreur(LookupError):
    pass


def lecteur_fiches(config: Config):
    """Lecture d'une fiche par le code des outils (adresse, conseiller), via le serveur MCP."""
    async def fiche_bien(bien_id: str) -> dict:
        async with Client(transport_catalogue(config)) as client:
            resultat = await client.call_tool("detail_bien", {"bien_id": bien_id}, raise_on_error=False)
        if resultat.is_error:
            raise FicheBienErreur(resultat.content[0].text)
        return resultat.data
    return fiche_bien
