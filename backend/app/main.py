"""FastAPI entry point: lifespan, static mounts, auth, JSON API routes.

Multi-tenant via GitHub OAuth + signed cookies. No DB: the OAuth access
token rides on a signed HttpOnly cookie, per-user PR snapshots live in
memory in :mod:`state`, and the per-user poller in :mod:`poller` runs
while the viewer is active or has watched PRs. Watched-PR readiness is
evaluated on the server after each poll; ntfy.sh notifications fire
from :mod:`watch` without any browser involvement.
"""
from __future__ import annotations

import logging
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

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

from . import auth, prefs, state
from .auth import Session, require_session
from .config import settings
from .cursor import CursorClient, CursorError
from .github import GitHubRateLimitError
from .linear import LinearClient, LinearError
from .poller import build_user_client, poll_once, start_poller_for
from .serialize import serialize_dashboard
from .watch import WATCHED_KEY, clear_watch_seeds, seed_newly_watched

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
    await prefs.connect(settings.PREFS_DB_PATH)
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
        await prefs.close()
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
# Per-user preferences (synced localStorage equivalents)
# ---------------------------------------------------------------------------


@app.get("/api/prefs")
async def get_prefs(
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Return the signed-in viewer's synced preferences as a flat dict.

    Shape is ``{ "<localStorage key>": <decoded JSON value>, ... }`` --
    only keys the viewer has actually set are present, so the client
    falls back to its own defaults for anything missing.
    """
    values = await prefs.get_all(session.login)
    return JSONResponse(content=values)


@app.put("/api/prefs")
async def put_prefs(
    body: dict[str, Any],
    request: Request,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Upsert one or more of the viewer's preferences (last-write-wins).

    Body is ``{ "<key>": <value>, ... }``. Unknown keys or oversized
    values reject the whole batch with 400; nothing is partially written.

    When the watch list changes we start (or keep) the viewer's backend
    poller and seed readiness for newly added keys so an already-ready
    PR does not notify immediately.
    """
    login = session.login
    http_client: httpx.AsyncClient = request.app.state.http_client
    old_watched: set[str] = set()
    if WATCHED_KEY in body:
        existing = await prefs.get_all(login)
        raw = existing.get(WATCHED_KEY)
        if isinstance(raw, list):
            old_watched = {str(x) for x in raw}

    try:
        stored = await prefs.set_many(login, body)
    except prefs.PrefError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if WATCHED_KEY in body:
        new_raw = body.get(WATCHED_KEY)
        new_watched = (
            {str(x) for x in new_raw} if isinstance(new_raw, list) else set()
        )
        if new_watched:
            await state.remember_token(login, session.token)
            start_poller_for(login, session.token, http_client)
            added = new_watched - old_watched
            if added:
                snapshot = state.current_snapshot(login)
                await seed_newly_watched(login, added=added, prs=snapshot.prs)
        else:
            await clear_watch_seeds(login)

    return JSONResponse(content=stored)


# ---------------------------------------------------------------------------
# JSON API (gated)
# ---------------------------------------------------------------------------


@app.get("/api/dashboard")
async def dashboard(
    request: Request,
    reviewers: str | None = None,
    reviewer: str | None = None,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Everything the SPA needs for one render, as JSON.

    Starts (idempotently) the viewer's background poller and touches
    their keep-alive timestamp. On a cold cache we poll synchronously
    once so the first paint has data instead of waiting a full interval.
    ``reviewers`` is a comma-separated list of the viewer's tracked
    reviewers (sent by the client from localStorage); omit it to fall
    back to the deploy-wide default. ``reviewer`` is the legacy
    single-login param, still honoured for older cached clients.
    """
    login = session.login
    http_client: httpx.AsyncClient = app.state.http_client

    await state.touch(login)
    await state.remember_token(login, session.token)
    start_poller_for(login, session.token, http_client)

    # Cold cache (process just started, or this viewer was reaped): warm
    # it synchronously so the client doesn't render an empty board until
    # the next poll. Best-effort -- a rate limit is surfaced in the
    # payload's `error` field, not as a hard failure.
    if state.last_polled_at(login) is None:
        gh = build_user_client(session.token, http_client=http_client)
        try:
            await poll_once(gh, login=login, http_client=http_client)
        except GitHubRateLimitError:
            pass
        except Exception:
            log.exception("cold-start poll failed for %s", login)
        finally:
            await gh.aclose()

    # Prefer the multi-reviewer param; fall back to the legacy single-login
    # one so a client that hasn't reloaded the new bundle still works.
    reviewers_param = reviewers if reviewers is not None else reviewer

    snapshot = state.current_snapshot(login)
    payload = serialize_dashboard(
        prs=snapshot.prs,
        reviews=snapshot.incoming_reviews,
        reviewers_param=reviewers_param,
        last_polled_at=state.last_polled_at(login),
        error_message=state.current_error(login),
        error_reset_at=state.error_reset_at(login),
        poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
    )
    return JSONResponse(content=payload)


@app.get("/api/users/search")
async def search_users(
    q: str,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Typeahead for the reviewer picker: search GitHub users by login/name.

    Proxied through the backend so the viewer's OAuth token never reaches
    the browser. The client debounces keystrokes before hitting this. A
    blank query short-circuits to an empty list (no point querying GitHub
    for nothing); transport/search failures degrade to an empty list so the
    settings dialog never hard-errors mid-typing.
    """
    query = q.strip()
    if not query:
        return JSONResponse(content=[])
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        results = await gh.search_users(query, limit=8)
    except GitHubRateLimitError:
        return JSONResponse(content=[])
    except Exception:
        log.exception("user search failed for %r", query)
        return JSONResponse(content=[])
    return JSONResponse(content=results)


# Cloud-agent ids look like ``bc-<uuid>`` (v1) or ``bc_<slug>`` (legacy
# v0). Anchor + cap the charset so the path segment can't be coerced into
# a different Cursor API path (SSRF guard) before we interpolate it.
_AGENT_ID_RE = re.compile(r"^bc[-_][A-Za-z0-9-]{1,128}$")


@app.get("/api/cloud-agent/models")
async def cloud_agent_models(
    session: Session = Depends(require_session),
) -> JSONResponse:
    """List Cursor models available when launching a QA cloud agent."""
    if not settings.CURSOR_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Cursor isn't configured on the server (CURSOR_API_KEY unset).",
        )

    http_client: httpx.AsyncClient = app.state.http_client
    client = CursorClient(
        settings.CURSOR_API_KEY,
        http_client=http_client,
        base_url=settings.CURSOR_API_URL,
    )
    try:
        models = await client.list_models()
    except CursorError as exc:
        log.warning("cloud-agent model list failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("unexpected error listing cloud-agent models")
        raise HTTPException(status_code=502, detail=str(exc))

    return JSONResponse(
        content={
            "items": [
                {
                    "id": m["id"],
                    "displayName": m.get("displayName") or m["id"],
                    "description": m.get("description"),
                }
                for m in models
            ]
        }
    )


@app.get("/api/cloud-agent/{agent_id}")
async def cloud_agent_status(
    agent_id: str,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Read a linked cloud agent's run state for a PR card.

    The client stores the agent link locally (per PR) and polls this
    endpoint for the running/done badge. We proxy through the server so
    the shared ``CURSOR_API_KEY`` never reaches the browser. Returns
    ``{configured, state, status, url, pr_url, error}``; transport/lookup
    failures come back as ``state: "error"`` (HTTP 200) so the card can
    degrade quietly rather than blow up the dashboard.
    """
    if not settings.CURSOR_API_KEY:
        return JSONResponse(
            content={
                "configured": False,
                "state": "unknown",
                "status": None,
                "error": "Cursor isn't configured on the server (CURSOR_API_KEY unset).",
            }
        )
    if not _AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="Invalid cloud agent id.")

    http_client: httpx.AsyncClient = app.state.http_client
    client = CursorClient(
        settings.CURSOR_API_KEY,
        http_client=http_client,
        base_url=settings.CURSOR_API_URL,
    )
    try:
        result = await client.agent_run_state(agent_id)
    except CursorError as exc:
        log.info("cloud-agent lookup failed for %s: %s", agent_id, exc)
        return JSONResponse(
            content={
                "configured": True,
                "state": "error",
                "status": None,
                "error": str(exc),
            }
        )
    except Exception as exc:  # noqa: BLE001 - never let a poll break the card
        log.exception("unexpected error reading cloud agent %s", agent_id)
        return JSONResponse(
            content={
                "configured": True,
                "state": "error",
                "status": None,
                "error": str(exc),
            }
        )

    return JSONResponse(content={"configured": True, "error": None, **result})


@app.get("/api/cloud-agent/{agent_id}/video-url")
async def cloud_agent_video_url(
    agent_id: str,
    path: str,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Mint a short-lived presigned URL for a recorded walkthrough artifact.

    Fetched lazily when the user opens the video modal (the URL expires in
    ~15 min, so we don't bake it into the polled status). ``path`` is the
    artifact's workspace-relative path (must live under ``artifacts/``).
    """
    if not settings.CURSOR_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Cursor isn't configured on the server (CURSOR_API_KEY unset).",
        )
    if not _AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="Invalid cloud agent id.")
    if not path.startswith("artifacts/") or ".." in path:
        raise HTTPException(status_code=400, detail="Invalid artifact path.")

    http_client: httpx.AsyncClient = app.state.http_client
    client = CursorClient(
        settings.CURSOR_API_KEY,
        http_client=http_client,
        base_url=settings.CURSOR_API_URL,
    )
    try:
        result = await client.artifact_download_url(agent_id, path)
    except CursorError as exc:
        log.info("artifact url failed for %s (%s): %s", agent_id, path, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("unexpected error fetching artifact url for %s", agent_id)
        raise HTTPException(status_code=502, detail=str(exc))

    return JSONResponse(
        content={
            "url": result.get("url"),
            "expires_at": result.get("expiresAt"),
        }
    )


# Owner/name guard for the repo we hand to the Cursor API.
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_DEFAULT_QA_MODEL_ID = "composer-2.5"


class StartCloudAgentBody(BaseModel):
    """Body for ``POST /api/cloud-agent`` (launch a QA agent for a PR)."""

    prompt: str = Field(min_length=1, max_length=10_000)
    repo: str = Field(max_length=140)
    model_id: str | None = Field(default=None, max_length=200)


@app.post("/api/cloud-agent")
async def start_cloud_agent(
    body: StartCloudAgentBody,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Launch a Cursor cloud agent to QA a PR, proxied with the shared key.

    The client supplies the (editable) prompt and the PR's ``owner/name``
    repo. We launch in the repo's named Cursor-hosted cloud environment
    (``env.name == owner/name`` by convention) so the agent inherits the
    configured repo/setup/preview env, and return ``{id, url}`` so the card
    can immediately link itself to the new run.
    """
    if not settings.CURSOR_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Cursor isn't configured on the server (CURSOR_API_KEY unset).",
        )
    repo = body.repo.strip()
    if not _REPO_RE.match(repo):
        raise HTTPException(
            status_code=400, detail="Invalid repo (expected owner/name)."
        )
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    model_id = (body.model_id or "").strip() or _DEFAULT_QA_MODEL_ID

    http_client: httpx.AsyncClient = app.state.http_client
    client = CursorClient(
        settings.CURSOR_API_KEY,
        http_client=http_client,
        base_url=settings.CURSOR_API_URL,
    )
    try:
        result = await client.create_agent(
            prompt=prompt, env_name=repo, model_id=model_id
        )
    except CursorError as exc:
        log.warning("cloud-agent launch failed for %s: %s", repo, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("unexpected error launching cloud agent for %s", repo)
        raise HTTPException(status_code=502, detail=str(exc))

    log.info("launched cloud agent %s to QA %s", result["id"], repo)
    return JSONResponse(
        content={
            "id": result["id"],
            "url": result["url"],
            "name": result.get("name"),
        }
    )


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
        await poll_once(gh, login=session.login, http_client=http_client)
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


class MergeBody(BaseModel):
    """Body for ``POST /pulls/.../merge``.

    ``mark_linear_done`` asks the server to also move the PR's linked
    Linear ticket into its team's completed state after the merge lands.
    The flag is best-effort: a failure there never fails the merge, it's
    just reported back in the response so the UI can surface it.
    """

    mark_linear_done: bool = False
    # Optional client-provided ticket id (e.g. ENG-1234). When present we
    # prefer this over the in-memory snapshot lookup so merge-time races don't
    # lose the linked ticket reference.
    linear_ticket: str | None = Field(default=None, max_length=64)


@app.post("/pulls/{owner}/{repo}/{number}/merge")
async def merge_pr_endpoint(
    owner: str,
    repo: str,
    number: int,
    body: MergeBody | None = None,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Merge a PR via the GitHub REST API, then refresh the snapshot.

    Optionally (``mark_linear_done``) also marks the PR's linked Linear
    ticket done. Returns ``{merged, linear_done, linear_error}`` so the
    client can confirm the merge and surface any Linear hiccup without
    treating it as a hard failure.
    """
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    method = settings.MERGE_METHOD or "merge"
    try:
        await gh.merge_pr(owner, repo, number, method=method)
    except Exception as exc:
        log.exception("merge failed for %s/%s#%s", owner, repo, number)
        raise HTTPException(status_code=502, detail=str(exc))

    linear_done = False
    linear_error: str | None = None
    if body is not None and body.mark_linear_done:
        linear_done, linear_error = await _mark_linear_done_for_pr(
            session.login,
            owner,
            repo,
            number,
            http_client,
            linear_ticket=body.linear_ticket,
        )

    await _safe_poll_once(session.token, session.login)
    return JSONResponse(
        content={
            "merged": True,
            "linear_done": linear_done,
            "linear_error": linear_error,
        }
    )


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

    The reviewers are supplied by the client (from localStorage); falls
    back to ``settings.REVIEWER_LOGIN`` when absent/empty. ``reviewers``
    is the multi-reviewer list; ``reviewer`` is the legacy single-login
    field, still accepted for older cached clients. Per-login length cap
    matches GitHub's own login limit.
    """

    reviewers: list[str] | None = Field(default=None, max_length=50)
    reviewer: str | None = Field(default=None, max_length=39)


def _resolve_request_reviewers(body: RequestReviewBody | None) -> list[str]:
    """Pick the logins to request, layering body -> legacy field -> env."""
    raw: list[str] = []
    if body is not None and body.reviewers is not None:
        raw = list(body.reviewers)
    elif body is not None and body.reviewer:
        raw = [body.reviewer]
    if not raw and settings.REVIEWER_LOGIN:
        raw = settings.REVIEWER_LOGIN.split(",")
    seen: set[str] = set()
    out: list[str] = []
    for login in raw:
        cleaned = (login or "").strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


@app.post("/pulls/{owner}/{repo}/{number}/request-review", status_code=204)
async def request_review(
    owner: str,
    repo: str,
    number: int,
    body: RequestReviewBody | None = None,
    session: Session = Depends(require_session),
) -> Response:
    """Add the viewer's tracked reviewer(s) to the PR's requested reviewers."""
    reviewers = _resolve_request_reviewers(body)
    if not reviewers:
        raise HTTPException(
            status_code=400,
            detail=(
                "No reviewers configured. Pick one in SETTINGS or set "
                "REVIEWER_LOGIN on the server."
            ),
        )
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.request_reviewers(owner, repo, number, reviewers)
    except Exception as exc:
        log.exception(
            "request-review failed for %s/%s#%s -> %s",
            owner,
            repo,
            number,
            ", ".join(f"@{r}" for r in reviewers),
        )
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.get("/pulls/{owner}/{repo}/{number}/diff")
async def pr_diff(
    owner: str,
    repo: str,
    number: int,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Return a PR's per-file diffs for the review panel.

    Returns ``{body, files, head_sha}``. ``body`` is the PR's markdown
    description (``None`` when empty); ``head_sha`` is the tip commit of
    the PR branch (needed as ``commit_id`` for inline comments); each
    file entry is ``{filename, status, additions, deletions, patch,
    previous_filename}`` where ``patch`` is GitHub's unified-diff hunk
    text (``None`` for binaries / undiffable files). The viewer's own
    token is used so private repos resolve.
    """
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        details = await gh.fetch_pr_details(owner, repo, number)
        files = await gh.fetch_pr_diff(owner, repo, number)
    except Exception as exc:
        log.exception("fetch_pr_diff failed for %s/%s#%s", owner, repo, number)
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await gh.aclose()
    return JSONResponse(
        content={
            "body": details["body"],
            "files": files,
            "head_sha": details["head_sha"],
        }
    )


@app.get("/attachments")
async def proxy_attachment(
    url: str,
    session: Session = Depends(require_session),
) -> Response:
    """Resolve a GitHub ``user-attachments`` asset with the viewer's token.

    Images/videos uploaded into PR bodies live at
    ``https://github.com/user-attachments/assets/<uuid>``. Those require
    authentication and GitHub sets its session cookie ``SameSite=Lax``, so a
    cross-origin ``<img>``/``<video>`` from the SPA never sends it and the
    asset 404s. We fetch it server-side with the viewer's OAuth token;
    GitHub answers with a 302 to a short-lived *signed* S3 URL that the
    browser can then load directly (it also supports range requests, so
    ``<video>`` seeking works). The host/path allowlist keeps this from
    doubling as an open proxy/SSRF vector.
    """
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.startswith("/user-attachments/")
    ):
        raise HTTPException(status_code=400, detail="Unsupported attachment URL.")

    http_client: httpx.AsyncClient = app.state.http_client
    headers = {"Authorization": f"bearer {session.token}"}
    try:
        resp = await http_client.get(url, headers=headers, follow_redirects=False)
    except httpx.HTTPError as exc:
        log.warning("attachment proxy failed for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail="Failed to fetch attachment.")

    location = resp.headers.get("location")
    if resp.is_redirect and location:
        # Hand the browser the signed asset URL; don't stream bytes through us.
        return RedirectResponse(location, status_code=302)
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub returned {resp.status_code} for attachment.",
        )
    # Rare: GitHub served the asset inline. Pass the bytes straight through.
    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type"),
    )


class ApproveBody(BaseModel):
    """Body for ``POST /pulls/.../approve`` (optional review summary)."""

    body: str = Field(default="", max_length=10_000)


class ReviewBody(BaseModel):
    """Body for ``POST /pulls/.../review`` (verdict + optional summary)."""

    event: str = Field(pattern="^(APPROVE|REQUEST_CHANGES|COMMENT)$")
    body: str = Field(default="", max_length=10_000)


class PrCommentBody(BaseModel):
    """Body for ``POST /pulls/.../comment`` (generic conversation comment)."""

    body: str = Field(min_length=1, max_length=10_000)


class LineCommentBody(BaseModel):
    """Body for ``POST /pulls/.../line-comment`` (inline diff comment)."""

    commit_id: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=4_096)
    body: str = Field(min_length=1, max_length=10_000)
    line: int = Field(ge=1)
    side: str = Field(pattern="^(LEFT|RIGHT)$")
    start_line: int | None = Field(default=None, ge=1)
    start_side: str | None = Field(default=None, pattern="^(LEFT|RIGHT)$")


@app.post("/pulls/{owner}/{repo}/{number}/approve", status_code=204)
async def approve_pr_endpoint(
    owner: str,
    repo: str,
    number: int,
    body: ApproveBody | None = None,
    session: Session = Depends(require_session),
) -> Response:
    """Submit an APPROVE review on a PR, then refresh the snapshot."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.submit_review(
            owner,
            repo,
            number,
            "APPROVE",
            body=body.body if body is not None else "",
        )
    except Exception as exc:
        log.exception("approve failed for %s/%s#%s", owner, repo, number)
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.post("/pulls/{owner}/{repo}/{number}/review", status_code=204)
async def submit_review_endpoint(
    owner: str,
    repo: str,
    number: int,
    body: ReviewBody,
    session: Session = Depends(require_session),
) -> Response:
    """Submit a review verdict (APPROVE / REQUEST_CHANGES / COMMENT)."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.submit_review(owner, repo, number, body.event, body=body.body)
    except Exception as exc:
        log.exception(
            "submit_review (%s) failed for %s/%s#%s",
            body.event,
            owner,
            repo,
            number,
        )
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.post("/pulls/{owner}/{repo}/{number}/comment", status_code=204)
async def post_pr_comment(
    owner: str,
    repo: str,
    number: int,
    body: PrCommentBody,
    session: Session = Depends(require_session),
) -> Response:
    """Post a generic conversation comment on a PR."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.post_issue_comment(owner, repo, number, body.body)
    except Exception as exc:
        log.exception(
            "post_pr_comment failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.post("/pulls/{owner}/{repo}/{number}/line-comment", status_code=204)
async def post_line_comment(
    owner: str,
    repo: str,
    number: int,
    body: LineCommentBody,
    session: Session = Depends(require_session),
) -> Response:
    """Post a standalone inline review comment on a PR diff line/range."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.post_review_comment(
            owner,
            repo,
            number,
            commit_id=body.commit_id,
            path=body.path,
            body=body.body,
            line=body.line,
            side=body.side,
            start_line=body.start_line,
            start_side=body.start_side,
        )
    except Exception as exc:
        log.exception(
            "post_line_comment failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))

    await _safe_poll_once(session.token, session.login)
    return Response(status_code=204)


@app.get("/pulls/{owner}/{repo}/{number}/comments")
async def pr_human_comments(
    owner: str,
    repo: str,
    number: int,
    session: Session = Depends(require_session),
) -> JSONResponse:
    """Return unresolved human comments on a PR for the comments popover.

    Mirrors the filtering logic used by the background poller so the
    list of items matches the ``comments_human`` count on the PR card.
    Each entry: ``{id, type, author, body, url}`` where ``type`` is
    ``"review"`` (inline thread) or ``"issue"`` (conversation comment).
    """
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        comments = await gh.fetch_human_comments(
            owner,
            repo,
            number,
            viewer_login=session.login,
            bot_logins=settings.BOT_LOGINS,
        )
    except Exception as exc:
        log.exception(
            "fetch_human_comments failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await gh.aclose()
    return JSONResponse(content=comments)


class AckCommentBody(BaseModel):
    """Body for ``POST /pulls/.../ack-comment``."""

    comment_id: int
    comment_type: str = Field(pattern="^(review|issue)$")


@app.post("/pulls/{owner}/{repo}/{number}/ack-comment", status_code=204)
async def ack_comment(
    owner: str,
    repo: str,
    number: int,
    body: AckCommentBody,
    session: Session = Depends(require_session),
) -> Response:
    """Add a 👀 reaction to a PR comment, marking it acknowledged."""
    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.add_comment_reaction(
            owner, repo, body.comment_id, body.comment_type, content="eyes"
        )
    except Exception as exc:
        log.exception(
            "ack_comment failed for %s/%s#%s comment %s",
            owner,
            repo,
            number,
            body.comment_id,
        )
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await gh.aclose()
    return Response(status_code=204)


class ReplyCommentBody(BaseModel):
    """Body for ``POST /pulls/.../reply-comment``."""

    quoted_author: str = Field(max_length=39)
    quoted_body: str = Field(max_length=10_000)
    reply: str = Field(min_length=1, max_length=10_000)


@app.post("/pulls/{owner}/{repo}/{number}/reply-comment", status_code=204)
async def reply_comment(
    owner: str,
    repo: str,
    number: int,
    body: ReplyCommentBody,
    session: Session = Depends(require_session),
) -> Response:
    """Post a new PR comment that quotes an existing comment as context.

    The server builds a GitHub-markdown quoted block (first 6 lines of
    the original) followed by the viewer's reply text, then posts it as
    an issue-style comment so it appears in the PR conversation timeline.
    """
    lines = body.quoted_body.splitlines()
    quote_lines = "\n".join(f"> {line}" for line in lines[:6])
    if len(lines) > 6:
        quote_lines += "\n> …"
    full_body = f"{quote_lines}\n\n{body.reply}" if quote_lines else body.reply

    http_client: httpx.AsyncClient = app.state.http_client
    gh = build_user_client(session.token, http_client=http_client)
    try:
        await gh.post_issue_comment(owner, repo, number, full_body)
    except Exception as exc:
        log.exception(
            "reply_comment failed for %s/%s#%s", owner, repo, number
        )
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await gh.aclose()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _linear_identifier_from_url(linear_url: str | None) -> str | None:
    """Pull the ``ENG-1234`` identifier out of a ``.../issue/ENG-1234`` URL.

    The snapshot already carries the per-card Linear URL (built by
    ``GitHubClient._find_linear_url``); rather than re-scan the PR body we
    just lift the ticket id back out of that URL. Returns ``None`` when the
    URL is missing or doesn't look like a Linear issue link.
    """
    if not linear_url:
        return None
    marker = "/issue/"
    idx = linear_url.find(marker)
    if idx < 0:
        return None
    rest = linear_url[idx + len(marker):]
    # Identifier runs up to the next path/query separator.
    for sep in ("/", "?", "#"):
        cut = rest.find(sep)
        if cut >= 0:
            rest = rest[:cut]
    return rest or None


_LINEAR_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")


def _normalize_linear_identifier(identifier: str | None) -> str | None:
    """Normalize a client-provided Linear ticket id (e.g. ``eng-123``)."""
    raw = (identifier or "").strip().upper()
    if not raw:
        return None
    if not _LINEAR_IDENTIFIER_RE.match(raw):
        return None
    return raw


async def _mark_linear_done_for_pr(
    login: str,
    owner: str,
    repo: str,
    number: int,
    http_client: httpx.AsyncClient,
    *,
    linear_ticket: str | None = None,
) -> tuple[bool, str | None]:
    """Best-effort: mark the merged PR's linked Linear ticket done.

    Returns ``(done, error)``. ``error`` is a human-readable string when
    something went wrong (no key, no ticket, Linear rejected it); the
    caller passes it straight through to the client. Never raises.
    """
    if not settings.LINEAR_API_KEY:
        return False, "Linear isn't configured on the server (LINEAR_API_KEY unset)."

    identifier = _normalize_linear_identifier(linear_ticket)
    if identifier is None:
        full_repo = f"{owner}/{repo}"
        snapshot = state.current_snapshot(login)
        linear_url = next(
            (
                pr.linear_url
                for pr in snapshot.prs
                if pr.number == number and pr.repo == full_repo
            ),
            None,
        )
        identifier = _linear_identifier_from_url(linear_url)
    if not identifier:
        return False, "No Linear ticket is linked to this PR."

    client = LinearClient(settings.LINEAR_API_KEY, http_client=http_client)
    try:
        state_name = await client.mark_issue_done(identifier)
    except LinearError as exc:
        log.warning("mark Linear done failed for %s: %s", identifier, exc)
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001 - never let this fail the merge
        log.exception("unexpected error marking Linear done for %s", identifier)
        return False, str(exc)
    log.info("marked Linear %s done (state=%s)", identifier, state_name)
    return True, None


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
        await poll_once(gh, login=login, http_client=http_client)
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
