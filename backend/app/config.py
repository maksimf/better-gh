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

    # GitHub OAuth App credentials. Tokens flow through signed
    # HttpOnly cookies; there's no shared PAT anymore.
    GITHUB_OAUTH_CLIENT_ID: str = Field(
        default="",
        description=(
            "OAuth App Client ID. Register one at "
            "https://github.com/settings/developers (or your org's "
            "OAuth Apps page) with the authorization callback URL "
            "set to '{base}/auth/callback'."
        ),
    )
    GITHUB_OAUTH_CLIENT_SECRET: str = Field(
        default="",
        description="OAuth App Client Secret matching GITHUB_OAUTH_CLIENT_ID.",
    )
    GITHUB_OAUTH_REDIRECT_URL: str = Field(
        default="http://localhost:8000/auth/callback",
        description=(
            "Must match the Authorization callback URL configured on "
            "the GitHub OAuth App, byte for byte."
        ),
    )
    OAUTH_SCOPES: str = Field(
        default="repo,read:org",
        description=(
            "Comma-separated OAuth scopes requested at sign-in. "
            "'repo' grants private-repo PR visibility; 'read:org' lets "
            "GitHub resolve `is:pr review-requested:@me` across orgs."
        ),
    )
    SESSION_SECRET: str = Field(
        default="",
        description=(
            "Secret used to sign the session cookie. Generate one with "
            "`python -c 'import secrets; print(secrets.token_urlsafe(48))'`. "
            "Rotating it logs everyone out, which is the desired property."
        ),
    )
    SESSION_MAX_AGE_SECONDS: int = Field(
        default=30 * 24 * 60 * 60,
        ge=60,
        description="How long a signed session cookie stays valid (default 30 days).",
    )
    COOKIE_SECURE: bool = Field(
        default=False,
        description=(
            "Set to True in production so the session cookie is only "
            "sent over HTTPS. Local dev on http://localhost defaults to "
            "False so the cookie still makes it through."
        ),
    )
    DEV_LOGIN: bool = Field(
        default=False,
        description=(
            "LOCAL DEV ONLY. When True, exposes GET /auth/dev-login which "
            "mints a session straight from DEV_GITHUB_TOKEN, skipping the "
            "GitHub OAuth round-trip (whose callback URL points at prod). "
            "MUST stay False in any deployed environment."
        ),
    )
    DEV_GITHUB_TOKEN: str = Field(
        default="",
        description=(
            "LOCAL DEV ONLY. Personal access token used by /auth/dev-login "
            "to impersonate yourself without OAuth. Ignored unless "
            "DEV_LOGIN is True."
        ),
    )
    GITHUB_GRAPHQL_URL: str = Field(default="https://api.github.com/graphql")
    GITHUB_API_URL: str = Field(default="https://api.github.com")
    POLL_INTERVAL_SECONDS: int = Field(default=300, ge=1)
    IDLE_TTL_SECONDS: int = Field(
        default=900,
        ge=30,
        description=(
            "How long a viewer's per-user poller keeps running after their "
            "last /api/dashboard fetch. Viewers with watched PRs are never "
            "reaped, so the backend can keep polling for readiness after "
            "the browser tab closes. Defaults to ~3x the poll interval."
        ),
    )
    PREFS_DB_PATH: str = Field(
        default="data/better-gh.sqlite3",
        description=(
            "Filesystem path to the SQLite database that stores per-user "
            "preferences (the synced localStorage equivalents). Resolved "
            "relative to the backend working directory; point it at a "
            "mounted volume so preferences survive container restarts. Use "
            "':memory:' for an ephemeral store (tests)."
        ),
    )
    MAX_PRS: int = Field(default=50, ge=1, le=100)
    PREVIEW_COMMENT_PREFIX: str = Field(default="Preview Environment URL:")
    REVIEWER_LOGIN: str = Field(
        default="nicoraga1",
        description=(
            "Default GitHub login(s) to track on each PR card when the "
            "viewer hasn't configured their own. Comma-separate to track "
            "several reviewers. Empty string disables the feature."
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
    LINEAR_API_KEY: str = Field(
        default="",
        description=(
            "Linear personal API key (starts with 'lin_api_'). When set, the "
            "merge dialog offers a 'merge & mark Linear ticket done' option "
            "that moves the PR's linked issue into its team's completed "
            "workflow state. Leave empty to disable -- merging still works, "
            "but the mark-done action will report that it's unconfigured."
        ),
    )
    CURSOR_API_KEY: str = Field(
        default="",
        description=(
            "Cursor Cloud Agents API key (Cursor Dashboard -> Integrations / "
            "API Keys). When set, each PR card can be linked to a cloud agent "
            "QAing the PR and the server polls that agent's run state "
            "(running vs done) on the client's behalf. Shared across the "
            "deploy like LINEAR_API_KEY; the feature is simply off when unset."
        ),
    )
    CURSOR_API_URL: str = Field(
        default="https://api.cursor.com",
        description="Base URL for the Cursor Cloud Agents API.",
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
