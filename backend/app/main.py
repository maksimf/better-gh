"""FastAPI entry point: lifespan, static mounts, auth, JSON API routes.

Multi-tenant via GitHub OAuth + signed cookies. No DB: the OAuth access
token rides on a signed HttpOnly cookie, per-user PR snapshots live in
memory in :mod:`state`, and the per-user poller in :mod:`poller` only
runs while the viewer is actively fetching ``/api/dashboard`` (a request
keep-alive + idle reaper, since react-query stops polling when the tab
is hidden). The React SPA reads the snapshot back as JSON.
"""
from __future__ import annotations

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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, state
from .auth import Session, require_session
from .config import settings
from .github import GitHubRateLimitError
from .poller import build_user_client, poll_once, start_poller_for
from .serialize import serialize_dashboard

log = logging.getLogger("better_gh.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
ASSETS_DIR = DIST_DIR / "assets"
LOGIN_HTML = FRONTEND_DIR / "login.html"
STYLES_CSS = FRONTEND_DIR / "styles.css"
FAVICON_SVG = FRONTEND_DIR / "favicon.svg"
APPLE_TOUCH_ICON = FRONTEND_DIR / "apple-touch-icon.png"

# How often the idle reaper runs. The TTL itself lives in settings.
_REAPER_INTERVAL_SECONDS = 60.0


def _index_file() -> Path:
    """The HTML shell to serve for the dashboard.

    Prefer the Vite build (``frontend/dist/index.html``); fall back to
    the source ``frontend/index.html`` so the app still boots in dev /
    tests where no production build exists.
    """
    built = DIST_DIR / "index.html"
    return built if built.is_file() else FRONTEND_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    http_client = httpx.AsyncClient(timeout=30.0)
    app.state.http_client = http_client
    log.info(
        "ready (poll_interval=%ss, idle_ttl=%ss, max_prs=%s); per-user pollers "
        "spin up as viewers fetch /api/dashboard",
        settings.POLL_INTERVAL_SECONDS,
        settings.IDLE_TTL_SECONDS,
        settings.MAX_PRS,
    )
    try:
        async with state.reaper(
            ttl_seconds=settings.IDLE_TTL_SECONDS,
            interval_seconds=_REAPER_INTERVAL_SECONDS,
        ):
            yield
    finally:
        await state.shutdown()
        await http_client.aclose()


app = FastAPI(title="better-gh", lifespan=lifespan)


if ASSETS_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(ASSETS_DIR)),
        name="assets",
    )


# ---------------------------------------------------------------------------
# Static + landing
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def index(request: Request) -> Response:
    """Authenticated visitors get the SPA; everyone else lands on /login."""
    if auth.read_session(request) is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return FileResponse(str(_index_file()), media_type="text/html")


@app.get("/styles.css", include_in_schema=False)
async def styles() -> FileResponse:
    return FileResponse(str(STYLES_CSS), media_type="text/css")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg() -> FileResponse:
    return FileResponse(str(FAVICON_SVG), media_type="image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico() -> FileResponse:
    """Fallback for browsers that auto-fetch /favicon.ico (serve the SVG)."""
    return FileResponse(str(FAVICON_SVG), media_type="image/svg+xml")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon() -> FileResponse:
    return FileResponse(str(APPLE_TOUCH_ICON), media_type="image/png")


# ---------------------------------------------------------------------------
# OAuth + session
# ---------------------------------------------------------------------------


@app.get("/login", include_in_schema=False)
async def login(request: Request) -> Response:
    """Serve the "Sign in with GitHub" page, or bounce signed-in users home."""
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


@app.get("/auth/dev-login", include_in_schema=False)
async def dev_login(request: Request) -> Response:
    """LOCAL DEV ONLY: mint a session from DEV_GITHUB_TOKEN, skip OAuth."""
    if not settings.DEV_LOGIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    token = settings.DEV_GITHUB_TOKEN.strip()
    if not token:
        return _auth_error_response(
            "DEV_LOGIN is on but DEV_GITHUB_TOKEN is empty. Put a PAT in "
            "backend/.env to use the dev sign-in shortcut."
        )

    http_client: httpx.AsyncClient | None = getattr(
        app.state, "http_client", None
    )
    owns_client = http_client is None
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=30.0)
    try:
        login = await auth.fetch_viewer_login(token, http_client=http_client)
    except Exception as exc:
        log.exception("dev-login viewer lookup failed")
        return _auth_error_response(f"Dev sign-in failed: {exc}")
    finally:
        if owns_client:
            await http_client.aclose()

    log.warning("DEV_LOGIN: minting session for %s (OAuth bypassed)", login)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    auth.write_session(response, Session(token=token, login=login))
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
        # waiting for the idle reaper.
        background.add_task(state.drop_user, session.login)
    return response


@app.get("/me", include_in_schema=False)
async def me(session: Session = Depends(require_session)) -> dict[str, str]:
    """Tiny endpoint the React topbar uses to render the user chip."""
    return {
        "login": session.login,
        "avatar_url": f"https://github.com/{session.login}.png?size=80",
    }


# ---------------------------------------------------------------------------
# JSON API (gated)
# ---------------------------------------------------------------------------


@app.get("/api/dashboard")
async def dashboard(
    request: Request,
    reviewer: str | None = None,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Everything the SPA needs for one render, as JSON.

    Starts (idempotently) the viewer's background poller and touches
    their keep-alive timestamp. On a cold cache we poll synchronously
    once so the first paint has data instead of waiting a full interval.
    ``reviewer`` is the viewer's tracked reviewer (sent by the client
    from localStorage); omit it to fall back to the deploy-wide default.
    """
    login = session.login
    http_client: httpx.AsyncClient = app.state.http_client

    await state.touch(login)
    start_poller_for(login, session.token, http_client)

    # Cold cache (process just started, or this viewer was reaped): warm
    # it synchronously so the client doesn't render an empty board until
    # the next poll. Best-effort -- a rate limit is surfaced in the
    # payload's `error` field, not as a hard failure.
    if state.last_polled_at(login) is None:
        gh = build_user_client(session.token, http_client=http_client)
        try:
            await poll_once(gh, login=login)
        except GitHubRateLimitError:
            pass
        except Exception:
            log.exception("cold-start poll failed for %s", login)
        finally:
            await gh.aclose()

    snapshot = state.current_snapshot(login)
    payload = serialize_dashboard(
        prs=snapshot.prs,
        reviews=snapshot.incoming_reviews,
        reviewer_login=reviewer,
        last_polled_at=state.last_polled_at(login),
        error_message=state.current_error(login),
        error_reset_at=state.error_reset_at(login),
        poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
    )
    return JSONResponse(content=payload)


# ---------------------------------------------------------------------------
# Mutations (per-user GitHub client built per request)
# ---------------------------------------------------------------------------


@app.post("/refresh")
async def refresh(
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Force a fresh poll synchronously.

    Returns 200 with the new ``last_polled_at`` on success, or 502 with
    ``{message, reset_at}`` on a rate-limit error so the client can show
    the banner without losing the existing board.
    """
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await poll_once(gh, login=session.login)
    except GitHubRateLimitError as exc:
        log.warning(
            "manual /refresh hit rate limit for %s (reset_at=%s)",
            session.login,
            exc.reset_at,
        )
        reset_iso = (
            exc.reset_at.isoformat().replace("+00:00", "Z")
            if exc.reset_at
            else None
        )
        return JSONResponse(
            content={"message": str(exc), "reset_at": reset_iso},
            status_code=502,
        )
    except Exception as exc:
        log.exception("manual /refresh poll failed for %s", session.login)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await gh.aclose()

    polled = state.last_polled_at(session.login)
    return JSONResponse(
        content={
            "last_polled_at": (
                polled.isoformat().replace("+00:00", "Z") if polled else None
            )
        }
    )


@app.post("/pulls/{owner}/{repo}/{number}/merge", status_code=204)
async def merge_pr_endpoint(
    owner: str,
    repo: str,
    number: int,
    session: Session = Depends(require_session),
) -> Response:
    """Merge a PR via the GitHub REST API, then refresh the snapshot."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    method = settings.MERGE_METHOD or "merge"
    try:
        await gh.merge_pr(owner, repo, number, method=method)
    except Exception as exc:
        log.exception("merge failed for %s/%s#%s", owner, repo, number)
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.post("/pulls/{owner}/{repo}/{number}/ready-for-review", status_code=204)
async def mark_ready_for_review(
    owner: str,
    repo: str,
    number: int,
    session: Session = Depends(require_session),
) -> Response:
    """Flip a draft PR to "Ready for review", then refresh the snapshot."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.mark_pr_ready_for_review(owner, repo, number)
    except Exception as exc:
        log.exception(
            "mark-ready-for-review failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


class RequestReviewBody(BaseModel):
    """Body for ``POST /pulls/.../request-review``.

    The reviewer is supplied by the client (from localStorage); falls
    back to ``settings.REVIEWER_LOGIN`` when absent/empty. Length cap
    matches GitHub's own login limit.
    """

    reviewer: str | None = Field(default=None, max_length=39)


@app.post("/pulls/{owner}/{repo}/{number}/request-review", status_code=204)
async def request_review(
    owner: str,
    repo: str,
    number: int,
    body: RequestReviewBody | None = None,
    session: Session = Depends(require_session),
) -> Response:
    """Add the viewer's tracked reviewer to the PR's requested reviewers."""
    raw = (body.reviewer if body is not None else None) or settings.REVIEWER_LOGIN
    reviewer = (raw or "").strip()
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

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _safe_poll_once(token: str, login: str) -> None:
    """Best-effort refresh after a mutation so the next fetch is fresh."""
    http_client: httpx.AsyncClient | None = getattr(
        app.state, "http_client", None
    )
    if http_client is None:
        log.warning("post-mutation poll fired but lifespan not started yet")
        return
    gh = build_user_client(token, http_client=http_client)
    try:
        await poll_once(gh, login=login)
    except Exception:
        log.exception("post-mutation poll failed for %s", login)
    finally:
        await gh.aclose()


def _auth_error_response(message: str) -> Response:
    """Minimal HTML page shown when the OAuth dance falls over."""
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
    return Response(content=body, status_code=400, media_type="text/html")


def run() -> None:
    """Console-script entry point: ``better-gh`` runs uvicorn on 0.0.0.0:8000."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
