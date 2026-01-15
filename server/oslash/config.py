"""OSlash Local Server Configuration."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    # Google
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # Slack
    slack_client_id: Optional[str] = None
    slack_client_secret: Optional[str] = None

    # HubSpot
    hubspot_client_id: Optional[str] = None
    hubspot_client_secret: Optional[str] = None

    # Paths
    data_dir: Path = Path.home() / ".oslash"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "oslash.db"

    # Sync
    sync_interval_minutes: int = 15
    max_file_size_mb: int = 10

    # Search
    default_results_count: int = 10

    # Logging
    log_level: str = "INFO"

    def ensure_directories(self) -> None:
        """Create necessary directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

