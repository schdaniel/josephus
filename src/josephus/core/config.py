"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default database URL for development only - uses obvious placeholder credentials
_DEV_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/josephus"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = Field(
        default=None,
        description="API key for authenticating manual API requests. Required in production.",
    )

    # Database - default only allowed in development
    database_url: PostgresDsn | None = Field(default=None)

    @model_validator(mode="after")
    def validate_database_url(self) -> Self:
        """Ensure database_url is explicitly set in non-development environments."""
        if self.database_url is None:
            if self.environment != "development":
                raise ValueError(
                    "DATABASE_URL must be explicitly set in non-development environments. "
                    f"Current environment: {self.environment}"
                )
            # Use development default only in development mode
            self.database_url = PostgresDsn(_DEV_DATABASE_URL)
        return self

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # GitHub App
    github_app_id: int | None = None
    github_app_private_key: str | None = None
    github_webhook_secret: str | None = None

    # LLM Providers
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_provider: Literal["claude", "openai", "ollama"] = "claude"

    # Feature Flags
    enable_secret_scanning: bool = True
    max_repo_size_mb: int = 100
    max_context_tokens: int = 100_000


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
