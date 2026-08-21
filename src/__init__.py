__version__ = "0.0.1_alpha.3"

from pathlib import Path
from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.i18n import Language
from src.logging_setup import configure_logging

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppSettings(BaseSettings):
    """Define environment-backed configuration for the KOOK agent application."""

    kook_token: SecretStr
    api_key: SecretStr
    base_url: AnyHttpUrl
    llm_model_id: str = Field(min_length=1)
    think_parameter: str = Field(default="enable_thinking", min_length=1)
    agent_think_enabled: bool | None = None
    language: Language = "CN"
    workspace_root: Path = PROJECT_ROOT / "workspaces"
    max_attachment_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_artifact_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        """Configure application logging using the resolved workspace root."""
        configure_logging(self.workspace_root)

