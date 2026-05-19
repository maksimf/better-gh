"""Runtime configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings.

    All values can be overridden via environment variables (or a local
    ``.env`` next to the backend). See ``.env.example`` for the full list.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    GITHUB_TOKEN: str = Field(default="", description="GitHub PAT used for the GraphQL API.")
    GITHUB_GRAPHQL_URL: str = Field(default="https://api.github.com/graphql")
    GITHUB_API_URL: str = Field(default="https://api.github.com")
    POLL_INTERVAL_SECONDS: int = Field(default=300, ge=1)
    MAX_PRS: int = Field(default=50, ge=1, le=100)
    PREVIEW_COMMENT_PREFIX: str = Field(default="Preview Environment URL:")
    REVIEWER_LOGIN: str = Field(
        default="nicoraga1",
        description=(
            "GitHub login of the reviewer to track on each PR card. "
            "Empty string disables the feature."
        ),
    )
    MERGE_METHOD: str = Field(
        default="merge",
        description=(
            "GitHub merge method used by the per-card MERGE button. "
            "One of 'merge', 'squash', or 'rebase'."
        ),
    )
    LINEAR_TICKET_PREFIX: str = Field(
        default="ENG-",
        description=(
            "Prefix used when scanning PR titles/bodies for Linear ticket "
            "references (e.g. 'ENG-' matches 'ENG-1234'). Leave empty to "
            "disable the per-card Linear button."
        ),
    )
    LINEAR_WORKSPACE_URL: str = Field(
        default="https://linear.app/clearest",
        description=(
            "Base URL of your Linear workspace. The per-card Linear button "
            "links to '{LINEAR_WORKSPACE_URL}/issue/{TICKET}'."
        ),
    )
    BOT_LOGINS: frozenset[str] = Field(
        default_factory=lambda: frozenset(
            {"cursor", "cursor[bot]", "coderabbitai", "coderabbitai[bot]"}
        )
    )

    @field_validator("BOT_LOGINS", mode="before")
    @classmethod
    def _parse_bot_logins(cls, value: object) -> frozenset[str]:
        if value is None or value == "":
            return frozenset()
        if isinstance(value, str):
            parts = [p.strip().lower() for p in value.split(",")]
            return frozenset(p for p in parts if p)
        if isinstance(value, (list, tuple, set, frozenset)):
            return frozenset(str(p).strip().lower() for p in value if str(p).strip())
        raise TypeError(f"Cannot parse BOT_LOGINS from {type(value).__name__}")


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


settings: Settings = _load_settings()
