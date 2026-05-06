"""Parse the preview-environment comment posted by CI to extract the URL.

The actual comment that ships in the wild looks like::

    <!-- preview-env-comment -->
    ### Preview Environment

    **URL:** https://pr-234.preview.example.com
    **Status:** Deployed
    **Commit:** `7f56a5c`

So we (a) detect that this comment IS the preview comment via either the
HTML marker or the "Preview Environment" header, and then (b) parse the
``Key: Value`` lines tolerantly (markdown bold, italics, backticks,
markdown link wrappers, autolink ``<...>``).

Pure functions; trivially unit-testable.
"""
from __future__ import annotations

import re

_MARKER_HTML_COMMENT = re.compile(
    r"<!--\s*preview[\s\-_]*env(?:ironment)?[\s\-_]*comment\s*-->",
    re.IGNORECASE,
)
_MARKER_HEADER = re.compile(
    r"(?m)^\s*#{1,6}\s*preview\s+environment\b",
    re.IGNORECASE,
)
_LEGACY_INLINE = re.compile(
    r"(?im)^\s*\**\s*preview\s+environment\s+url\s*\**\s*:",
)

_KEY_VALUE_LINE = re.compile(
    r"""(?mx)
    ^\s*
    [\*\_~`]*\s*                     # leading markdown decoration (e.g. **)
    (?P<key>[A-Za-z][A-Za-z0-9 _\-]*?)
    \s*[\*\_~`]*\s*:\s*[\*\_~`]*\s*  # ": " with optional markdown wrap
    (?P<value>.+?)
    \s*[\*\_~`]*\s*$
    """,
)

_URL_RE = re.compile(r"https?://[^\s<>)`\]]+", re.IGNORECASE)

_INLINE_RE = re.compile(
    r"(?is)preview\s+environment\s+url\s*:?\s*(?P<url>https?://\S+)"
    r"\s+.*?status\s*:?\s*(?P<status>\w+)"
)


def looks_like_preview_comment(body: str) -> bool:
    """Heuristic: does this comment body look like the preview-env comment?"""
    if not body:
        return False
    return bool(
        _MARKER_HTML_COMMENT.search(body)
        or _MARKER_HEADER.search(body)
        or _LEGACY_INLINE.search(body)
    )


def extract_preview_url(comment_body: str, prefix: str = "") -> str | None:
    """Return the deployed preview URL, or ``None``.

    ``prefix`` is accepted for backward compatibility but no longer used —
    we now key off the comment's structural markers, which are far more
    reliable than a single inline prefix string.

    Returns ``None`` when:
    - the comment doesn't look like a preview comment,
    - no ``URL:`` line is present,
    - or the ``Status:`` line doesn't include the word "Deployed".
    """
    del prefix  # accepted but ignored
    if not comment_body:
        return None

    inline = _INLINE_RE.search(comment_body)
    if inline:
        if "deployed" in inline.group("status").lower():
            return inline.group("url").rstrip(",.;)")
        return None

    if not looks_like_preview_comment(comment_body):
        return None

    url: str | None = None
    status: str = ""

    for match in _KEY_VALUE_LINE.finditer(comment_body):
        key = _normalise_key(match.group("key"))
        value = _strip_value(match.group("value"))
        if key in {"url", "previewurl", "previewenvironmenturl", "preview"}:
            url = url or _extract_url(value)
        elif key == "status":
            status = value.lower()

    if not url:
        # Some comments embed only the URL inline (no key); fall back to the
        # first URL we can find in the body, but only if a Status: line said
        # Deployed.
        url_match = _URL_RE.search(comment_body)
        if url_match:
            url = url_match.group(0)

    if not url:
        return None
    if "deployed" not in status:
        return None
    return url


def _normalise_key(raw: str) -> str:
    return re.sub(r"[\s_\-]+", "", raw).lower()


def _strip_value(raw: str) -> str:
    """Pull a clean value out of common markdown wrappers."""
    candidate = raw.strip()
    candidate = candidate.strip("*_~`")
    candidate = candidate.strip()
    md_link = re.match(r"\[[^\]]*\]\(([^)]+)\)", candidate)
    if md_link:
        candidate = md_link.group(1).strip()
    if candidate.startswith("<") and candidate.endswith(">"):
        candidate = candidate[1:-1].strip()
    return candidate.rstrip(",.;)")


def _extract_url(value: str) -> str | None:
    """Find the first URL in a stripped value (handles trailing markdown)."""
    if not value:
        return None
    if _URL_RE.fullmatch(value):
        return value
    found = _URL_RE.search(value)
    return found.group(0) if found else None
