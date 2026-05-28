"""FastAPI entry point: lifespan, static mounts, auth, HTML + SSE routes.

Multi-tenant via GitHub OAuth + signed cookies. No DB: the OAuth access
token rides on a signed HttpOnly cookie, per-user PR snapshots live in
memory in :mod:`state`, and the per-user poller in :mod:`poller` only
runs while the viewer has at least one open SSE connection.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import auth, state
from .auth import (
    Session,
    require_session,
    require_session_or_redirect,
)
from .config import settings
from .github import GitHubRateLimitError
from .poller import build_user_client, poll_once, start_poller_for
from .render import render_error_banner, render_meta, render_prs, render_reviews

log = logging.getLogger("better_gh.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
LOGIN_HTML = FRONTEND_DIR / "login.html"
STYLES_CSS = FRONTEND_DIR / "styles.css"
FAVICON_SVG = FRONTEND_DIR / "favicon.svg"
APPLE_TOUCH_ICON = FRONTEND_DIR / "apple-touch-icon.png"

REVIEWER_PREF_COOKIE = "reviewer_pref"


def _resolve_reviewer(request: Request, login: str) -> str | None:
    """Three-tier lookup for the viewer's tracked reviewer.

    1. ``UserState.reviewer_login`` if set (populated on SSE connect
       or by ``POST /settings/reviewer``).
    2. ``reviewer_pref`` cookie (rides on htmx XHR fetches before SSE
       has had a chance to populate UserState on a fresh page load).
    3. ``None`` -- ``render.effective_reviewer`` then falls back to
       ``settings.REVIEWER_LOGIN`` (the deploy-wide default).

    Returns the raw value (``None`` / ``""`` / login). The render
    helper normalises further.
    """
    cached = state.get_reviewer(login)
    if cached is not None:
        return cached
    raw_cookie = request.cookies.get(REVIEWER_PREF_COOKIE)
    if raw_cookie is None:
        return None
    return raw_cookie


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    http_client = httpx.AsyncClient(timeout=30.0)
    app.state.http_client = http_client
    log.info(
        "ready (poll_interval=%ss, max_prs=%s); per-user pollers will spin up "
        "as viewers sign in",
        settings.POLL_INTERVAL_SECONDS,
        settings.MAX_PRS,
    )
    try:
        yield
    finally:
        await state.shutdown()
        await http_client.aclose()


app = FastAPI(title="better-gh", lifespan=lifespan)


if FRONTEND_DIR.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


# ---------------------------------------------------------------------------
# Static + landing
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def index(request: Request) -> FileResponse:
    """Authenticated visitors get the dashboard; everyone else lands on /login."""
    if auth.read_session(request) is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return FileResponse(str(INDEX_HTML), media_type="text/html")


@app.get("/styles.css", include_in_schema=False)
async def styles() -> FileResponse:
    return FileResponse(str(STYLES_CSS), media_type="text/css")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg() -> FileResponse:
    return FileResponse(str(FAVICON_SVG), media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico() -> FileResponse:
    """Fallback for browsers that auto-fetch /favicon.ico.

    We just hand them the SVG too -- modern browsers accept it, older
    ones get a clean 200 instead of a 404 spamming the console.
    """
    return FileResponse(str(FAVICON_SVG), media_type="image/svg+xml")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon() -> FileResponse:
    """180x180 PNG used by iOS for the "Add to Home Screen" icon."""
    return FileResponse(str(APPLE_TOUCH_ICON), media_type="image/png")


# ---------------------------------------------------------------------------
# OAuth + session
# ---------------------------------------------------------------------------


@app.get("/login", include_in_schema=False)
async def login(request: Request) -> Response:
    """Serve the "Sign in with GitHub" landing page, or bounce signed-in users home."""
    if auth.read_session(request) is not None:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return FileResponse(str(LOGIN_HTML), media_type="text/html")


@app.get("/auth/start", include_in_schema=False)
async def auth_start() -> Response:
    """Kick off the OAuth flow: stash a CSRF token, redirect to GitHub."""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    csrf = auth.issue_oauth_state(response)
    response.headers["Location"] = auth.oauth_authorize_url(csrf)
    return response


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(request: Request) -> Response:
    """OAuth callback: verify CSRF, exchange code, set session cookie."""
    code = request.query_params.get("code") or ""
    echoed_state = request.query_params.get("state") or ""
    error = request.query_params.get("error")
    if error:
        log.warning("OAuth callback returned error=%s", error)
        return _auth_error_response(f"GitHub returned: {error}")
    if not code:
        return _auth_error_response("Missing OAuth code.")
    if not auth.verify_oauth_state(request, echoed_state):
        return _auth_error_response(
            "OAuth state mismatch (possible CSRF or expired sign-in)."
        )

    http_client: httpx.AsyncClient | None = getattr(
        app.state, "http_client", None
    )
    if http_client is None:
        # Lifespan hasn't run yet (test edge case); spin up a one-shot.
        http_client = httpx.AsyncClient(timeout=30.0)
        owns_client = True
    else:
        owns_client = False

    try:
        token = await auth.exchange_code(code, echoed_state, http_client=http_client)
        login = await auth.fetch_viewer_login(token, http_client=http_client)
    except Exception as exc:
        log.exception("OAuth code exchange failed")
        return _auth_error_response(f"Sign-in failed: {exc}")
    finally:
        if owns_client:
            await http_client.aclose()

    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    auth.write_session(response, Session(token=token, login=login))
    auth.clear_oauth_state(response)
    return response


@app.post("/logout", include_in_schema=False)
async def logout(
    request: Request,
    background: BackgroundTasks,
) -> Response:
    """Drop the session cookie + any per-user in-memory state."""
    session = auth.read_session(request)
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    auth.clear_session(response)
    if session is not None:
        # Cancel the poller and free the snapshot ASAP rather than
        # waiting for the next SSE disconnect.
        background.add_task(state.drop_if_idle, session.login)
    return response


class ReviewerSetting(BaseModel):
    """Body for ``POST /settings/reviewer``.

    ``reviewer`` may be a GitHub login (string) or ``null`` to revert
    to the deploy-wide default. We accept a length cap matching
    GitHub's own login limit (39 chars) plus a permissive character
    set so we reject obvious garbage early without hand-rolling a
    validation regex that fights an edge case nobody hits in
    practice.
    """

    reviewer: str | None = Field(default=None, max_length=39)


@app.post("/settings/reviewer", status_code=204)
async def set_reviewer_setting(
    payload: ReviewerSetting,
    session: Session = Depends(require_session),
) -> Response:
    """Update the viewer's tracked reviewer + re-broadcast immediately.

    Caches the choice on ``UserState`` and pushes a fresh ``prs`` SSE
    event to all of this viewer's open tabs so the chip / column
    placement updates without waiting for the next poll. The frontend
    is also expected to write the same value to ``localStorage`` + a
    ``reviewer_pref`` cookie so it survives page reloads and rides
    on htmx fetches before the next SSE connect.
    """
    changed, _ = await state.set_reviewer(session.login, payload.reviewer)
    if changed:
        reviewer = state.get_reviewer(session.login)
        snapshot = state.current_snapshot(session.login)
        await state.broadcast(
            session.login, "prs", render_prs(snapshot.prs, reviewer)
        )
    return Response(status_code=204)


@app.get("/me", include_in_schema=False)
async def me(session: Session = Depends(require_session)) -> dict[str, str]:
    """Tiny endpoint the frontend topbar uses to render the user chip.

    Avatar URL leans on GitHub's per-login PNG redirect so we don't
    spend an extra GraphQL query on every page load.
    """
    return {
        "login": session.login,
        "avatar_url": f"https://github.com/{session.login}.png?size=80",
    }


# ---------------------------------------------------------------------------
# HTML fragments (gated)
# ---------------------------------------------------------------------------


@app.get("/prs.html", response_class=HTMLResponse)
async def prs_fragment(
    request: Request,
    session: Session = Depends(require_session),
) -> HTMLResponse:
    reviewer = _resolve_reviewer(request, session.login)
    html = render_prs(state.current_snapshot(session.login).prs, reviewer)
    return HTMLResponse(content=html)


@app.get("/reviews.html", response_class=HTMLResponse)
async def reviews_fragment(
    session: Session = Depends(require_session),
) -> HTMLResponse:
    """Slim PR rows for the "Reviewing" tab (review-requested from viewer)."""
    html = render_reviews(state.current_snapshot(session.login).incoming_reviews)
    return HTMLResponse(content=html)


@app.get("/status", response_class=HTMLResponse)
async def status_fragment(
    session: Session = Depends(require_session),
) -> HTMLResponse:
    html = render_meta(state.last_polled_at(session.login))
    return HTMLResponse(content=html)


@app.get("/repos")
async def repos_summary(
    session: Session = Depends(require_session),
) -> list[dict[str, object]]:
    """Distinct repos across the user's PRs + their incoming reviews."""
    counts: dict[str, int] = {}
    snapshot = state.current_snapshot(session.login)
    for pr in snapshot.prs:
        counts[pr.repo] = counts.get(pr.repo, 0) + 1
    for pr in snapshot.incoming_reviews:
        counts[pr.repo] = counts.get(pr.repo, 0) + 1
    return [
        {"repo": repo, "count": count}
        for repo, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------


@app.get("/events")
async def events(
    request: Request,
    session: Session = Depends(require_session),
) -> EventSourceResponse:
    login = session.login
    token = session.token
    http_client: httpx.AsyncClient = app.state.http_client
    # Read the reviewer preference cookie *before* opening the
    # streaming response so we can prime UserState before the very
    # first bootstrap render. Skip if no cookie -- the cached value
    # from a prior connect (if any) wins; otherwise we fall back to
    # the env default at render time.
    cookie_reviewer = request.cookies.get(REVIEWER_PREF_COOKIE)

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        # Register the subscriber queue first so any broadcast that
        # fires during the bootstrap window (or kicked off by the
        # poller's very first poll below) lands on the queue.
        async with state.subscriber(login) as queue:
            if cookie_reviewer is not None:
                await state.set_reviewer(login, cookie_reviewer)
            reviewer = state.get_reviewer(login)
            start_poller_for(login, token, render_prs, http_client)
            snapshot = state.current_snapshot(login)
            yield {
                "event": "prs",
                "data": _flatten(render_prs(snapshot.prs, reviewer)),
            }
            yield {
                "event": "reviews",
                "data": _flatten(render_reviews(snapshot.incoming_reviews)),
            }
            yield {
                "event": "meta",
                "data": _flatten(render_meta(state.last_polled_at(login))),
            }
            yield {
                "event": "gh-error",
                "data": _flatten(state.current_error(login)),
            }
            try:
                while True:
                    try:
                        payload = await asyncio.wait_for(
                            queue.get(),
                            timeout=state.HEARTBEAT_INTERVAL_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": ""}
                        continue
                    yield payload
            finally:
                # Tear down the per-user poller once the last subscriber
                # disconnects. Run after the `async with` so the queue
                # is already removed and the subscriber count reads 0.
                asyncio.create_task(state.drop_if_idle(login))

    return EventSourceResponse(event_stream(), ping=15)


# ---------------------------------------------------------------------------
# Mutations (per-user GitHub client built per request)
# ---------------------------------------------------------------------------


@app.post("/refresh", response_class=HTMLResponse)
async def refresh(
    request: Request,
    session: Session = Depends(require_session),
) -> HTMLResponse:
    """Force a fresh poll synchronously and return the new PR fragment.

    On a rate-limit error we return 502 with the banner HTML in the
    body plus ``HX-Retarget``/``HX-Reswap`` so the frontend swaps it
    into the error banner without wiping the existing PR list.
    """
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await poll_once(gh, render_prs, login=session.login)
    except GitHubRateLimitError as exc:
        log.warning(
            "manual /refresh hit rate limit for %s (reset_at=%s)",
            session.login,
            exc.reset_at,
        )
        banner = render_error_banner(str(exc), exc.reset_at)
        return HTMLResponse(
            content=banner,
            status_code=502,
            headers={
                "HX-Retarget": "#error-banner",
                "HX-Reswap": "innerHTML",
            },
        )
    except Exception as exc:
        log.exception("manual /refresh poll failed for %s", session.login)
        raise HTTPException(status_code=502, detail=str(exc))
    reviewer = _resolve_reviewer(request, session.login)
    html = render_prs(state.current_snapshot(session.login).prs, reviewer)
    return HTMLResponse(content=html)


@app.post(
    "/pulls/{owner}/{repo}/{number}/merge",
    status_code=204,
)
async def merge_pr_endpoint(
    owner: str,
    repo: str,
    number: int,
    background: BackgroundTasks,
    session: Session = Depends(require_session),
) -> Response:
    """Merge a PR via the GitHub REST API."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    method = settings.MERGE_METHOD or "merge"
    try:
        await gh.merge_pr(owner, repo, number, method=method)
    except Exception as exc:
        log.exception("merge failed for %s/%s#%s", owner, repo, number)
        raise HTTPException(status_code=502, detail=str(exc))

    background.add_task(_safe_poll_once, session.token, session.login)
    return Response(status_code=204)


@app.post(
    "/pulls/{owner}/{repo}/{number}/ready-for-review",
    status_code=204,
)
async def mark_ready_for_review(
    owner: str,
    repo: str,
    number: int,
    background: BackgroundTasks,
    session: Session = Depends(require_session),
) -> Response:
    """Flip a draft PR to "Ready for review" via GitHub GraphQL."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.mark_pr_ready_for_review(owner, repo, number)
    except Exception as exc:
        log.exception(
            "mark-ready-for-review failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))

    background.add_task(_safe_poll_once, session.token, session.login)
    return Response(status_code=204)


@app.post(
    "/pulls/{owner}/{repo}/{number}/request-review",
    status_code=204,
)
async def request_review(
    owner: str,
    repo: str,
    number: int,
    background: BackgroundTasks,
    request: Request,
    session: Session = Depends(require_session),
) -> Response:
    """Add the viewer's tracked reviewer to the PR's requested reviewers.

    Reviewer login comes from per-user state (settings modal) with the
    cookie / ``REVIEWER_LOGIN`` env var as fallback -- same precedence
    as the per-card chip in the rendered HTML, so what the user sees on
    the button is what gets requested when they click it.
    """
    raw = _resolve_reviewer(request, session.login)
    reviewer = (raw or settings.REVIEWER_LOGIN or "").strip()
    if not reviewer:
        raise HTTPException(
            status_code=400,
            detail=(
                "No reviewer configured. Pick one in SETTINGS or set "
                "REVIEWER_LOGIN on the server."
            ),
        )
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.request_reviewer(owner, repo, number, reviewer)
    except Exception as exc:
        log.exception(
            "request-review failed for %s/%s#%s -> @%s",
            owner,
            repo,
            number,
            reviewer,
        )
        raise HTTPException(status_code=502, detail=str(exc))

    background.add_task(_safe_poll_once, session.token, session.login)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _safe_poll_once(token: str, login: str) -> None:
    http_client: httpx.AsyncClient | None = getattr(
        app.state, "http_client", None
    )
    if http_client is None:
        log.warning("background poll fired but lifespan not started yet")
        return
    gh = build_user_client(token, http_client=http_client)
    try:
        await poll_once(gh, render_prs, login=login)
    except Exception:
        log.exception("background poll failed for %s", login)


def _flatten(html: str) -> str:
    return html.replace("\r\n", "\n").replace("\n", "")


def _auth_error_response(message: str) -> HTMLResponse:
    """Minimal HTML page shown when the OAuth dance falls over.

    We render this inline rather than templating it because it's only
    seen by a tiny fraction of users and shouldn't depend on the
    frontend pipeline being healthy.
    """
    nonce = secrets.token_hex(4)
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    body = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Sign in failed - BETTER//GH</title>"
        "<link rel='stylesheet' href='/styles.css'></head>"
        "<body class='auth-error-page'>"
        "<main class='auth-error'>"
        "<h1>SIGN-IN FAILED</h1>"
        f"<p class='auth-error-msg'>{safe}</p>"
        "<p><a class='btn btn--refresh' href='/login'>TRY AGAIN</a></p>"
        f"<p class='auth-error-ref'>ref {nonce}</p>"
        "</main></body></html>"
    )
    return HTMLResponse(content=body, status_code=400)


def run() -> None:
    """Console-script entry point: ``better-gh`` runs uvicorn on 0.0.0.0:8000."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
