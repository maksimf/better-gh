"""Jinja2 environment + render helpers for PR fragments."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import settings
from .model import PR

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
    iso = when.isoformat().replace("+00:00", "Z")
    return (
        'LAST UPDATED '
        f'<span class="last-updated-relative" data-iso="{iso}">just now</span>'
    )
