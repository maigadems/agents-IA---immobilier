"""Configuration de l'agent, lue depuis l'environnement (fichier .env a la racine)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")
# pas de banniere publicitaire de pydantic-ai : nos traces suffisent
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def _chemin(valeur: str) -> Path:
    """Chemin absolu : les chemins relatifs du .env partent de la racine du depot."""
    p = Path(valeur)
    return p if p.is_absolute() else RACINE / p


def _entier(nom: str, defaut: int) -> int:
    try:
        return int(os.getenv(nom, defaut))
    except ValueError as exc:
        raise ValueError(f"La variable {nom} doit etre un entier.") from exc


@dataclass(frozen=True)
class Config:
    # modele
    fournisseur: str = field(default_factory=lambda: os.getenv("MODEL_PROVIDER", "ollama"))
    modele: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "qwen2.5:7b"))
    base_url: str | None = field(default_factory=lambda: os.getenv("MODEL_BASE_URL") or None)
    api_key: str | None = field(default_factory=lambda: os.getenv("MODEL_API_KEY") or None)
    temperature: float = field(default_factory=lambda: float(os.getenv("MODEL_TEMPERATURE", "0")))

    # boucle de l'agent
    max_etapes: int = field(default_factory=lambda: _entier("AGENT_MAX_ETAPES", 8))
    max_appels_outils: int = field(default_factory=lambda: _entier("AGENT_MAX_APPELS_OUTILS", 12))
    retries_outils: int = field(default_factory=lambda: _entier("AGENT_RETRIES_OUTILS", 2))

    # serveur MCP du catalogue : "stdio" (lance le script) ou une URL http
    mcp_catalogue: str = field(default_factory=lambda: os.getenv("MCP_SERVER_URL", "stdio"))

    # traces
    dossier_traces: Path = field(default_factory=lambda: _chemin(os.getenv("TRACES_DIR", "traces")))

    # pipeline (ex 5) : etat des conversations, indexe par fil Gmail
    fichier_etat: Path = field(default_factory=lambda: _chemin(os.getenv("ETAT_FICHIER",
                                                                          "etat/conversations.json")))
    intervalle_s: int = field(default_factory=lambda: _entier("PIPELINE_INTERVALLE_S", 30))

    timezone: str =field(default_factory=lambda: os.getenv("TIMEZONE", "Africa/Dakar"))
