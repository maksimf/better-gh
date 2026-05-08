"""Jinja2 environment + render helpers for PR fragments."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import settings
from .model import PR, ReviewPR

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
    auto_reload=True,
)


def render_prs(prs: list[PR]) -> str:
    """Render the PR-card fragment that goes into ``#pr-stream``.

    Looks the template up on every call so template edits are picked up
    without restarting uvicorn (Jinja does an mtime check internally).
    """
    return env.get_template("prs.html").render(
        prs=prs,
        reviewer_login=settings.REVIEWER_LOGIN,
    )


def render_reviews(prs: list[ReviewPR]) -> str:
    """Render the slim review-row fragment that goes into ``#reviews-stream``.

    Used by the "Reviewing" tab; one row per PR with title + checks +
    conflicts. Filtering by repo happens client-side via the same
    ignore-list as the main board.
    """
    return env.get_template("reviews.html").render(prs=prs)


def render_meta(when: datetime | None) -> str:
    """Render the "last updated" footer fragment.

    Carries the ISO timestamp on a ``data-iso`` attribute so the client-side
    ticker can recompute the human relative text (every minute) without a
    server round-trip. The textContent is just an initial placeholder.
    """
    if when is None:
        return (
            'LAST UPDATED <span class="last-updated-relative">never</span>'
        )
    iso = _iso_z(when)
    return (
        'LAST UPDATED '
        f'<span class="last-updated-relative" data-iso="{iso}">just now</span>'
    )


def render_error_banner(message: str, reset_at: datetime | None) -> str:
    """Render the error-banner fragment shown above the board.

    ``reset_at`` is optional: when set, the fragment carries it on
    ``data-iso`` so the client-side ticker can render and refresh a
    "try again in X mins" hint without another round-trip. When unknown,
    we deliberately omit the time hint rather than guessing.
    """
    safe_message = escape(message)
    if reset_at is None:
        hint_html = ""
    else:
        iso = _iso_z(reset_at)
        hint_html = (
            ' <span class="error-banner-hint">'
            f'Try again <span class="error-banner-relative" data-iso="{iso}">'
            "soon</span>.</span>"
        )
    return (
        '<div class="error-banner-inner" role="alert">'
        '<span class="error-banner-icon" aria-hidden="true">!</span>'
        '<span class="error-banner-text">'
        f'<strong>{safe_message}</strong>{hint_html}'
        "</span>"
        "</div>"
    )


def _iso_z(when: datetime) -> str:
    return when.isoformat().replace("+00:00", "Z")
