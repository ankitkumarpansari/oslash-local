"""Configuration management for OSlash Local."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OSLASH_",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Server Configuration
    # ==========================================================================
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # ==========================================================================
    # LLM Configuration (supports OpenAI or Ollama)
    # ==========================================================================
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider: 'openai' or 'ollama'",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
        alias="OPENAI_API_KEY",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model",
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions",
    )
    chat_model: str = Field(
        default="qwen2.5:7b",
        description="Chat model for Q&A (e.g., 'gpt-4o-mini' for OpenAI, 'qwen2.5:7b' for Ollama)",
    )
    chat_temperature: float = Field(
        default=0.7,
        ge=0,
        le=2,
        description="Chat model temperature",
    )
    max_tokens: int = Field(
        default=2000,
        ge=1,
        le=128000,
        description="Maximum tokens for chat response",
    )
    
    # ==========================================================================
    # Ollama Configuration
    # ==========================================================================
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL",
    )

    # ==========================================================================
    # Path Configuration
    # ==========================================================================
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".oslash",
        description="Data directory for all persistent storage",
    )

    @property
    def chroma_dir(self) -> Path:
        """ChromaDB storage directory."""
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        """SQLite database path."""
        return self.data_dir / "oslash.db"

    @property
    def logs_dir(self) -> Path:
        """Logs directory."""
        return self.data_dir / "logs"

    # ==========================================================================
    # Sync Configuration
    # ==========================================================================
    sync_interval_minutes: int = Field(
        default=15,
        ge=1,
        description="Auto-sync interval in minutes",
    )
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file size to index in MB",
    )
    batch_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Batch size for sync operations",
    )

    # ==========================================================================
    # Search Configuration
    # ==========================================================================
    default_results_count: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default number of search results",
    )
    max_results_count: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Maximum number of search results",
    )
    similarity_threshold: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Minimum similarity score for results",
    )

    # ==========================================================================
    # Chunking Configuration
    # ==========================================================================
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=8000,
        description="Target chunk size in characters",
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=1000,
        description="Overlap between chunks",
    )

    # ==========================================================================
    # OAuth Configuration (loaded from env)
    # ==========================================================================
    google_client_id: Optional[str] = Field(
        default=None,
        description="Google OAuth client ID",
    )
    google_client_secret: Optional[str] = Field(
        default=None,
        description="Google OAuth client secret",
    )
    slack_client_id: Optional[str] = Field(
        default=None,
        description="Slack OAuth client ID",
    )
    slack_client_secret: Optional[str] = Field(
        default=None,
        description="Slack OAuth client secret",
    )
    hubspot_client_id: Optional[str] = Field(
        default=None,
        description="HubSpot OAuth client ID",
    )
    hubspot_client_secret: Optional[str] = Field(
        default=None,
        description="HubSpot OAuth client secret",
    )
    hubspot_api_key: Optional[str] = Field(
        default=None,
        description="HubSpot Private App Access Token (alternative to OAuth)",
    )

    # ==========================================================================
    # Validators
    # ==========================================================================
    @field_validator("data_dir", mode="after")
    @classmethod
    def ensure_data_dir_exists(cls, v: Path) -> Path:
        """Ensure data directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("log_level", mode="after")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v

    # ==========================================================================
    # Helper Methods
    # ==========================================================================
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key)
    
    def use_ollama(self) -> bool:
        """Check if using Ollama for chat."""
        return self.llm_provider.lower() == "ollama"

    def has_google_oauth(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(self.google_client_id and self.google_client_secret)

    def has_slack_oauth(self) -> bool:
        """Check if Slack OAuth is configured."""
        return bool(self.slack_client_id and self.slack_client_secret)

    def has_hubspot_oauth(self) -> bool:
        """Check if HubSpot OAuth is configured."""
        return bool(self.hubspot_client_id and self.hubspot_client_secret)

    def has_hubspot_api_key(self) -> bool:
        """Check if HubSpot API key is configured."""
        return bool(self.hubspot_api_key)

    def has_hubspot(self) -> bool:
        """Check if HubSpot is configured (OAuth or API key)."""
        return self.has_hubspot_oauth() or self.has_hubspot_api_key()

    def get_configured_sources(self) -> list[str]:
        """Get list of configured sources."""
        sources = []
        if self.has_google_oauth():
            sources.extend(["gdrive", "gmail"])
        if self.has_slack_oauth():
            sources.append("slack")
        if self.has_hubspot():
            sources.append("hubspot")
        return sources


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function to reload settings (clears cache)
def reload_settings() -> Settings:
    """Reload settings (useful after env changes)."""
    get_settings.cache_clear()
    return get_settings()
