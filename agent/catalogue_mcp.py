"""Connexion de l'agent au serveur MCP du catalogue (client MCP).

L'agent n'a plus aucune fonction locale d'acces au catalogue : tout passe par le serveur.
- MCP_SERVER_URL=stdio           -> l'agent lance mcp_server/mcp_server.py en sous-processus
- MCP_SERVER_URL=http://.../mcp  -> l'agent se connecte a un serveur deja demarre (HTTP)
"""

from __future__ import annotations

import os
import sys

from fastmcp.client.transports import PythonStdioTransport, StreamableHttpTransport
from pydantic_ai.mcp import MCPToolset

from agent.config import RACINE, Config

SCRIPT_SERVEUR = RACINE / "mcp_server" / "mcp_server.py"


def toolset_catalogue(config: Config) -> MCPToolset:
    if config.mcp_catalogue == "stdio":
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        transport = PythonStdioTransport(
            SCRIPT_SERVEUR,
            args=["--transport", "stdio"],
            env=env,
            cwd=str(RACINE),
            python_cmd=sys.executable,
        )
    elif config.mcp_catalogue.startswith(("http://", "https://")):
        transport = StreamableHttpTransport(config.mcp_catalogue)
    else:
        raise ValueError(f"MCP_SERVER_URL invalide : {config.mcp_catalogue!r} (stdio ou URL http).")

    return MCPToolset(
        transport,
        id="catalogue",
        tool_error_behavior="retry",
        max_retries=config.retries_outils,
    )
