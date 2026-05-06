"""FastAPI entry point: lifespan, static mounts, HTML + SSE routes."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import state
from .config import settings
from .github import GitHubClient
from .poller import poll_forever, poll_once
from .render import render_meta, render_prs

log = logging.getLogger("better_gh.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
STYLES_CSS = FRONTEND_DIR / "styles.css"
FAVICON_SVG = FRONTEND_DIR / "favicon.svg"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    http_client = httpx.AsyncClient(timeout=30.0)
    gh = GitHubClient(
        token=settings.GITHUB_TOKEN,
        graphql_url=settings.GITHUB_GRAPHQL_URL,
        api_url=settings.GITHUB_API_URL,
        max_prs=settings.MAX_PRS,
        http_client=http_client,
    )
    app.state.http_client = http_client
    app.state.github = gh

    try:
        await poll_once(gh, render_prs)
    except Exception:
        log.exception("initial poll failed; serving an empty snapshot")

    poll_task = asyncio.create_task(
        poll_forever(gh, render_prs, settings.POLL_INTERVAL_SECONDS),
        name="better-gh.poller",
    )
    app.state.poll_task = poll_task
    log.info(
        "poller started (interval=%ss, max_prs=%s)",
        settings.POLL_INTERVAL_SECONDS,
        settings.MAX_PRS,
    )

    try:
        yield
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except (asyncio.CancelledError, Exception):
            pass
        await http_client.aclose()


app = FastAPI(title="better-gh", lifespan=lifespan)


if FRONTEND_DIR.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
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


@app.get("/prs.html", response_class=HTMLResponse)
async def prs_fragment() -> HTMLResponse:
    html = render_prs(state.current_snapshot().prs)
    return HTMLResponse(content=html)


@app.get("/status", response_class=HTMLResponse)
async def status_fragment() -> HTMLResponse:
    html = render_meta(state.last_polled_at())
    return HTMLResponse(content=html)


@app.get("/repos")
async def repos_summary() -> list[dict[str, object]]:
    """Distinct repos in the current snapshot, sorted by PR count desc, name asc.

    Used by the settings modal to populate the "ignore repos" list. Stays in
    JSON shape (rather than HTML) so the frontend can iterate cleanly.
    """
    counts: dict[str, int] = {}
    for pr in state.current_snapshot().prs:
        counts[pr.repo] = counts.get(pr.repo, 0) + 1
    return [
        {"repo": repo, "count": count}
        for repo, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


@app.get("/events")
async def events() -> EventSourceResponse:
    async def event_stream() -> AsyncIterator[dict[str, str]]:
        initial_prs = render_prs(state.current_snapshot().prs)
        yield {"event": "prs", "data": _flatten(initial_prs)}
        initial_meta = render_meta(state.last_polled_at())
        yield {"event": "meta", "data": _flatten(initial_meta)}
        async for evt in state.subscribe():
            yield evt

    return EventSourceResponse(event_stream(), ping=15)


@app.post("/refresh", response_class=HTMLResponse)
async def refresh() -> HTMLResponse:
    """Force a fresh poll synchronously and return the new PR fragment.

    Unlike the background poller, this awaits the GitHub query so the
    HTTP response only comes back once the snapshot is up-to-date. The
    body is identical to ``GET /prs.html`` so the frontend swaps it
    straight into ``#pr-stream``. The poller's normal SSE broadcast still
    fires (no-op if data is unchanged), keeping other tabs in sync.
    """
    gh: GitHubClient | None = getattr(app.state, "github", None)
    if gh is None:
        raise HTTPException(
            status_code=503,
            detail="GitHub client is not initialised yet.",
        )
    try:
        await poll_once(gh, render_prs)
    except Exception as exc:
        log.exception("manual /refresh poll failed")
        raise HTTPException(status_code=502, detail=str(exc))
    html = render_prs(state.current_snapshot().prs)
    return HTMLResponse(content=html)


@app.post(
    "/pulls/{owner}/{repo}/{number}/request-review",
    status_code=204,
)
async def request_review(
    owner: str,
    repo: str,
    number: int,
    background: BackgroundTasks,
) -> Response:
    """Add ``settings.REVIEWER_LOGIN`` to the PR's requested reviewers.

    Best-effort: returns 204 on success, surfaces upstream HTTP errors as
    502, and 400 when the feature is disabled (no REVIEWER_LOGIN set).
    Triggers a background poll on success so the chip flips fast.
    """
    reviewer = settings.REVIEWER_LOGIN
    if not reviewer:
        raise HTTPException(
            status_code=400,
            detail="REVIEWER_LOGIN is empty; the request-review feature is disabled.",
        )
    gh: GitHubClient | None = getattr(app.state, "github", None)
    if gh is None:
        raise HTTPException(
            status_code=503,
            detail="GitHub client is not initialised yet.",
        )
    try:
        await gh.request_reviewer(owner, repo, number, reviewer)
    except Exception as exc:
        log.exception(
            "request-review failed for %s/%s#%s -> @%s", owner, repo, number, reviewer
        )
        raise HTTPException(status_code=502, detail=str(exc))

    background.add_task(_safe_poll_once)
    return Response(status_code=204)


async def _safe_poll_once() -> None:
    gh: GitHubClient | None = getattr(app.state, "github", None)
    if gh is None:
        log.warning("/refresh fired but GitHubClient not initialised yet")
        return
    try:
        await poll_once(gh, render_prs)
    except Exception:
        log.exception("manual /refresh poll failed")


def _flatten(html: str) -> str:
    return html.replace("\r\n", "\n").replace("\n", "")


def run() -> None:
    """Console-script entry point: ``better-gh`` runs uvicorn on 0.0.0.0:8000."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
