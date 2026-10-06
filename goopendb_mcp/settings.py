from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Runtime configuration. Values come from the environment first, then from
    `.env` / `.env.production` in the project root (the latter is kept for
    backward compatibility with existing deployments).
    """

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env.production", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MCP transport
    HOST: str = "0.0.0.0"
    PORT: int = 13005
    MCP_PATH: str = "/mcp"
    # Stateless JSON responses scale horizontally and need no sticky sessions.
    STATELESS_HTTP: bool = True
    JSON_RESPONSE: bool = True

    # GoOpenDB
    GO_OPENSEARCH_DATABASE_URL: str = Field(
        description="Base URL of GoOpenDB, e.g. http://go-opensearch-database:8000"
    )
    # Advanced search goes through a reranker, so allow it a generous budget.
    REQUEST_TIMEOUT_SECONDS: float = 60.0

    # IANA timezone for `current_time`; empty means the container's local zone.
    TIMEZONE: str = ""

    LOG_LEVEL: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
