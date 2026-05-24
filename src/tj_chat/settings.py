"""Configuration settings for the LLM Agent Chat service.

Uses pydantic-settings to load configuration from environment variables
with the TJ_CHAT_ prefix.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatSettings(BaseSettings):
    """Configuration for the LLM agent chat service.

    All settings can be overridden via environment variables with the
    TJ_CHAT_ prefix (e.g., TJ_CHAT_LM_STUDIO_URL).
    """

    model_config = SettingsConfigDict(env_prefix="TJ_CHAT_")

    lm_studio_url: str = "http://localhost:1234/v1"
    model_name: str | None = None
    token_limit: int = 4096
    connection_timeout: int = 10
    response_timeout: int = 120
    default_author: str | None = None
    project_path: Path = Path("/app/project")
    project_file: str = "project.tjp"
    reports_path: Path = Path("/app/reports")
    tj_docs_path: Path = Path("/app/tj-docs")
    web_port: int = 8080
