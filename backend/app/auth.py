"""GitHub OAuth (Web Application Flow) + signed-cookie sessions.

The whole "no database" trick lives here. We never persist anything
server-side:

* The OAuth access token is encoded into a signed, HttpOnly cookie
  (``gh_session``). The cookie body is a small JSON object
  ``{"token": ..., "login": ...}`` signed with ``SESSION_SECRET`` via
  ``itsdangerous`` so a tampered cookie is rejected and a stolen one
  carries no extra capabilities (anyone holding it already has the GH
  token, which is the same auth material).
* The CSRF ``state`` parameter for the OAuth round-trip rides on its
  own short-lived cookie (``gh_oauth_state``) signed the same way. We
  compare it against the ``state`` GitHub echoes back instead of
  keeping a server-side nonce set.

That means a process restart logs no one out and ``state.py`` can
forget about per-user persistence entirely -- everything we need to
authenticate a request is in the request itself.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

log = logging.getLogger("better_gh.auth")

SESSION_COOKIE = "gh_session"
OAUTH_STATE_COOKIE = "gh_oauth_state"
_OAUTH_STATE_MAX_AGE = 10 * 60  # 10 minutes for the round-trip

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"


@dataclass(frozen=True)
class Session:
    """Everything we know about an authenticated viewer.

    ``token`` is the raw GitHub OAuth access token; we never persist it
    server-side, just round-trip it through the signed cookie.
    ``login`` is the GitHub login (lower-cased) we fetched once at
    sign-in time -- avoids an extra ``viewer { login }`` round-trip on
    every authenticated request.
    """

    token: str
    login: str


def _session_serializer() -> URLSafeTimedSerializer:
    """Built lazily so a missing SESSION_SECRET surfaces at sign-in time
    rather than at import time (handier for ``--help`` / tests)."""
    if not settings.SESSION_SECRET:
        raise RuntimeError(
            "SESSION_SECRET is empty; refusing to sign session cookies. "
            "Generate one with `python -c 'import secrets; "
            "print(secrets.token_urlsafe(48))'` and put it in .env."
        )
    return URLSafeTimedSerializer(settings.SESSION_SECRET, salt="gh-session")


def _oauth_state_serializer() -> URLSafeTimedSerializer:
    if not settings.SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET is empty; cannot sign OAuth state cookie.")
    return URLSafeTimedSerializer(settings.SESSION_SECRET, salt="gh-oauth-state")


def read_session(request: Request) -> Session | None:
    """Return the verified session from the cookie, or ``None``.

    Bad/expired signatures and malformed payloads all collapse to
    ``None`` so the caller treats them as "not authenticated" rather
    than blowing up.
    """
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        payload = _session_serializer().loads(
            raw, max_age=settings.SESSION_MAX_AGE_SECONDS
        )
    except SignatureExpired:
        log.info("session cookie expired")
        return None
    except BadSignature:
        log.warning("session cookie failed signature check (tampered or rotated key)")
        return None
    if not isinstance(payload, dict):
        return None
    token = payload.get("token")
    login = payload.get("login")
    if not isinstance(token, str) or not isinstance(login, str):
        return None
    if not token or not login:
        return None
    return Session(token=token, login=login.lower())


def write_session(response: Response, session: Session) -> None:
    """Sign + set the session cookie on ``response``."""
    payload = {"token": session.token, "login": session.login}
    signed = _session_serializer().dumps(payload)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    """Expire both auth cookies (session + any leftover OAuth state)."""
    for key in (SESSION_COOKIE, OAUTH_STATE_COOKIE):
        response.delete_cookie(
            key=key,
            path="/",
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
        )


def issue_oauth_state(response: Response) -> str:
    """Generate a fresh CSRF state token and stash a signed copy in a cookie.

    Returned value is what we hand to GitHub via ``?state=``; the
    cookie holds a signed copy that the callback compares against the
    echoed value. No server-side nonce table required.
    """
    state = secrets.token_urlsafe(32)
    signed = _oauth_state_serializer().dumps(state)
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=signed,
        max_age=_OAUTH_STATE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return state


def verify_oauth_state(request: Request, echoed: str) -> bool:
    """Constant-time compare the cookie-signed state against ``echoed``.

    Bad/expired signatures, missing cookies, and mismatched values all
    return ``False``. Callers should refuse to exchange the code on
    ``False``.
    """
    raw = request.cookies.get(OAUTH_STATE_COOKIE)
    if not raw or not echoed:
        return False
    try:
        original = _oauth_state_serializer().loads(raw, max_age=_OAUTH_STATE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    if not isinstance(original, str):
        return False
    return secrets.compare_digest(original, echoed)


def clear_oauth_state(response: Response) -> None:
    """Best-effort delete of the OAuth state cookie after we're done with it."""
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )


def oauth_authorize_url(state: str) -> str:
    """Build the URL we redirect the browser to for the "Allow" prompt."""
    if not settings.GITHUB_OAUTH_CLIENT_ID:
        raise RuntimeError(
            "GITHUB_OAUTH_CLIENT_ID is empty; register an OAuth App at "
            "https://github.com/settings/developers and set it in .env."
        )
    params = {
        "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URL,
        "scope": settings.OAUTH_SCOPES,
        "state": state,
        # ``allow_signup=true`` matches GitHub's default but documents intent.
        "allow_signup": "true",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    code: str, state: str, *, http_client: httpx.AsyncClient
) -> str:
    """Trade the OAuth ``code`` for an access token. Raises on failure.

    We pass ``state`` through to GitHub too (it ignores it server-side
    but the docs recommend it). The real CSRF check already happened in
    :func:`verify_oauth_state` before this is called.
    """
    if not settings.GITHUB_OAUTH_CLIENT_ID or not settings.GITHUB_OAUTH_CLIENT_SECRET:
        raise RuntimeError(
            "GITHUB_OAUTH_CLIENT_ID/SECRET are required to exchange OAuth codes."
        )
    payload = {
        "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
        "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URL,
        "state": state,
    }
    headers = {"Accept": "application/json"}
    resp = await http_client.post(_TOKEN_URL, data=payload, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"GitHub OAuth token exchange failed: {resp.status_code} {resp.text}"
        )
    body: dict[str, Any] = resp.json() or {}
    if body.get("error"):
        raise RuntimeError(
            f"GitHub OAuth error: {body.get('error')} "
            f"({body.get('error_description') or 'no description'})"
        )
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("GitHub OAuth response did not include an access_token.")
    return token


async def fetch_viewer_login(
    token: str, *, http_client: httpx.AsyncClient
) -> str:
    """One tiny GraphQL ``viewer { login }`` call to identify the signed-in user.

    Cached into the session cookie so we don't re-hit GitHub on every
    authenticated request just to learn the viewer's own login.
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    resp = await http_client.post(
        settings.GITHUB_GRAPHQL_URL,
        headers=headers,
        json={"query": "{ viewer { login } }"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"GitHub viewer lookup failed: {resp.status_code} {resp.text}"
        )
    body = resp.json() or {}
    if body.get("errors"):
        raise RuntimeError(f"GitHub viewer lookup errors: {body['errors']}")
    login = ((body.get("data") or {}).get("viewer") or {}).get("login")
    if not isinstance(login, str) or not login:
        raise RuntimeError("GitHub viewer lookup did not return a login.")
    return login


def require_session(request: Request) -> Session:
    """FastAPI dependency for JSON / API routes.

    Returns the verified session or raises ``401`` so fetch-based
    clients (and HTMX swaps) see a clean error instead of a redirect.
    Use :func:`require_session_or_redirect` for full-page HTML routes
    where a 302 to ``/login`` is the right UX.
    """
    session = read_session(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in.",
        )
    return session


def require_session_or_redirect(request: Request) -> Session:
    """FastAPI dependency for top-level HTML routes.

    Returns the verified session, or short-circuits the request with a
    302 to ``/login`` by raising ``HTTPException`` with a Location
    header. (FastAPI doesn't have a first-class "redirect from
    dependency" sugar; raising with ``headers={"Location": ...}``
    captures the same effect.)
    """
    session = read_session(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Not signed in.",
            headers={"Location": "/login"},
        )
    return session


def redirect_to_login() -> RedirectResponse:
    """Convenience used by ``GET /`` when the visitor has no session."""
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
