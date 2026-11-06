from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toda la configuración sale del archivo .env (prefijo PYME_)."""

    model_config = SettingsConfigDict(env_prefix="PYME_", env_file=".env", extra="ignore")

    # Proveedor de LLM del asistente conversacional: "ollama" (real) o "fake" (demo sin modelo)
    llm_provider: Literal["ollama", "fake"] = "ollama"
    api_key: SecretStr | None = None
    # Clave de la consola del analista (decisiones humanas). En producción: SSO + RBAC.
    analyst_key: SecretStr | None = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_timeout: float = 60.0

    # Narrador de textos del journey: "plantilla" (determinista) o "crewai" (equipo de agentes)
    narrator: Literal["plantilla", "crewai"] = "plantilla"
    # Modelo para CrewAI en formato LiteLLM: "ollama/llama3.2:1b", "anthropic/<modelo>", etc.
    crewai_model: str = "ollama/llama3.2:1b"
    crewai_base_url: str | None = None

    # Marca: el logo y los colores se cambian en la carpeta brand/ (ver README)
    brand_name: str = "Periferia IT Group"
    brand_tagline: str = "Liquidez Factura · Banca Pyme"
    brand_dir: str = "brand"
