"""Construction du modele : Ollama en local ou toute API compatible OpenAI (palier gratuit)."""

from __future__ import annotations

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from agent.config import Config

OLLAMA_URL_DEFAUT = "http://localhost:11434/v1"


def construire_modele(config: Config) -> Model:
    """Renvoie le modele configure. Les deux options supportent l'appel d'outils natif."""
    reglages = ModelSettings(temperature=config.temperature)

    if config.fournisseur == "ollama":
        fournisseur = OllamaProvider(base_url=config.base_url or OLLAMA_URL_DEFAUT)
    elif config.fournisseur == "openai_compatible":
        if not config.base_url:
            raise ValueError("MODEL_BASE_URL est obligatoire avec MODEL_PROVIDER=openai_compatible.")
        if not config.api_key or config.api_key == "changeme":
            raise ValueError("MODEL_API_KEY manquant dans .env.")
        fournisseur = OpenAIProvider(base_url=config.base_url, api_key=config.api_key)
    else:
        raise ValueError(
            f"MODEL_PROVIDER inconnu : {config.fournisseur!r} (attendu : ollama ou openai_compatible)."
        )

    return OpenAIChatModel(config.modele, provider=fournisseur, settings=reglages)
