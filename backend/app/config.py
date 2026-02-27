"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = "Librarian API"
    database_url: str = "postgresql+psycopg://librarian:librarian@localhost:5432/librarian"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.2"
    openai_embedding_model: str = "text-embedding-3-small"
    enable_pgvector: bool = False
    enable_resolution_llm_disambiguation: bool = False
    global_resolution_max_candidates: int = 500
    openai_timeout_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
