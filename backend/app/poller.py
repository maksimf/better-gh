"""Per-user background poll loop that keeps each viewer's snapshot fresh.

Lifecycle is tied to the SSE subscriber refcount in :mod:`state` -- the
``/events`` handler calls :func:`start_poller_for` the first time a
viewer connects and ``state.drop_if_idle`` cancels the task the moment
their last subscriber disconnects. No always-on background loop;
nothing runs for signed-out users.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

import httpx

from . import state
from .config import settings
from .github import GitHubClient, GitHubRateLimitError
from .model import PR
from .render import render_error_banner, render_meta, render_reviews

log = logging.getLogger("better_gh.poller")

# render(prs, reviewer_login) -> html. Reviewer is supplied per-user so
# the per-card "R" chip, "Request review" button, and APPROVED-column
# placement all line up with that viewer's tracked reviewer.
RenderFn = Callable[[list[PR], str | None], str]


async def poll_once(client: GitHubClient, render: RenderFn, *, login: str) -> bool:
    """Fetch PRs + incoming reviews for ``login``, swap into their snapshot, broadcast.

    Always broadcasts a ``meta`` event (so the "last updated" footer
    ticks on every successful poll). Broadcasts ``prs`` when the
    viewer's PRs changed and ``reviews`` when the incoming-reviews
    list changed -- either independently. Returns ``True`` when the
    viewer's PR fragment was re-broadcast (kept for backwards-compat
    with callers that gate on that signal; the reviews update is
    fire-and-forget over SSE).

    Rate-limit failures are surfaced as a ``gh-error`` SSE event (and
    the exception is re-raised so callers like ``/refresh`` can return
    a 502). The banner persists until the previous error's
    ``reset_at`` actually expires -- a single intermittent successful
    poll mid-window no longer flickers it away.
    """
    try:
        prs, reviews, rate_limit = await client.fetch_dashboard_snapshot()
    except GitHubRateLimitError as exc:
        html = render_error_banner(str(exc), exc.reset_at)
        if await state.set_error(login, html, exc.reset_at):
            # ``gh-error`` (not ``error``) -- EventSource's native error
            # event collides with a custom event named "error" and
            # crashes the htmx SSE extension on reconnect attempts.
            await state.broadcast(login, "gh-error", html)
        log.warning(
            "poll[%s]: rate limited (reset_at=%s)", login, exc.reset_at
        )
        raise

    # NOTE: we intentionally *don't* attach_stacks here -- the
    # co-column layout depends on the viewer's tracked reviewer, so
    # stack attachment lives in ``render_prs`` (called below + on each
    # request). The snapshot stays reviewer-agnostic so it can be
    # cached once per viewer regardless of their reviewer choice.
    new_snapshot = state.Snapshot(prs=prs, incoming_reviews=reviews)
    prs_changed, reviews_changed = await state.set_snapshot(login, new_snapshot)
    polled_at = await state.mark_polled(login)
    reviewer_login = state.get_reviewer(login)

    # Only clear the error banner once the previous reset window has
    # actually expired. Mid-window successes (typical of GitHub's
    # secondary "anti-burst" limits) used to flicker the banner away
    # before the user could read it; now it persists until the limit
    # truly lifts.
    prev_reset = state.error_reset_at(login)
    if prev_reset is None or prev_reset <= datetime.now(timezone.utc):
        if await state.set_error(login, ""):
            await state.broadcast(login, "gh-error", "")

    if prs_changed:
        await state.broadcast(login, "prs", render(prs, reviewer_login))
    if reviews_changed:
        await state.broadcast(login, "reviews", render_reviews(reviews))
    log.info(
        "poll[%s]: %d PRs (%s), %d reviews (%s)",
        login,
        len(prs),
        "changed" if prs_changed else "unchanged",
        len(reviews),
        "changed" if reviews_changed else "unchanged",
    )
    if rate_limit is not None:
        log.info(
            "poll[%s]: rateLimit cost=%s remaining=%s/%s reset=%s",
            login,
            rate_limit.get("cost"),
            rate_limit.get("remaining"),
            rate_limit.get("limit"),
            rate_limit.get("resetAt"),
        )
    await state.broadcast(login, "meta", render_meta(polled_at))
    return prs_changed


async def poll_forever(
    client: GitHubClient,
    render: RenderFn,
    interval_seconds: int,
    *,
    login: str,
) -> None:
    """Loop forever for ``login``; never exits on its own. Cancellation stops it."""
    try:
        while True:
            try:
                await poll_once(client, render, login=login)
            except asyncio.CancelledError:
                log.info("poller[%s] cancelled; exiting loop", login)
                raise
            except GitHubRateLimitError as exc:
                # Already broadcast as an error banner in poll_once; keep the
                # log line short so the loop doesn't spam stack traces while
                # we wait out the limit.
                log.warning(
                    "poll[%s] skipped: rate limited (reset_at=%s)",
                    login,
                    exc.reset_at,
                )
            except Exception:
                log.exception("poll[%s] failed", login)
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                log.info("poller[%s] cancelled during sleep; exiting loop", login)
                raise
    finally:
        # Drop our per-user GitHub client when the loop ends so the
        # connection it spawned is returned to the shared httpx pool
        # cleanly. Safe to call regardless of `_owns_client`.
        try:
            await client.aclose()
        except Exception:
            pass


def build_user_client(
    token: str, *, http_client: httpx.AsyncClient
) -> GitHubClient:
    """Construct a per-request / per-user :class:`GitHubClient`.

    We share the underlying ``httpx.AsyncClient`` (and thus its
    connection pool) across all viewers; only the auth token differs.
    """
    return GitHubClient(
        token=token,
        graphql_url=settings.GITHUB_GRAPHQL_URL,
        api_url=settings.GITHUB_API_URL,
        max_prs=settings.MAX_PRS,
        http_client=http_client,
    )


def start_poller_for(
    login: str,
    token: str,
    render: RenderFn,
    http_client: httpx.AsyncClient,
) -> asyncio.Task:
    """Ensure a background poller is running for ``login``; idempotent.

    Returns the existing task if one is already alive for this viewer;
    otherwise spawns ``poll_forever`` against a fresh per-user
    :class:`GitHubClient`. The caller (the ``/events`` handler) is
    responsible for tearing it down via ``state.drop_if_idle`` when
    the last subscriber leaves.
    """
    existing = state.get_poll_task(login)
    if existing is not None and not existing.done():
        return existing

    client = build_user_client(token, http_client=http_client)
    task = asyncio.create_task(
        poll_forever(
            client,
            render,
            settings.POLL_INTERVAL_SECONDS,
            login=login,
        ),
        name=f"better-gh.poller[{login}]",
    )
    state.set_poll_task(login, task)
    log.info(
        "poller[%s] started (interval=%ss, max_prs=%s)",
        login,
        settings.POLL_INTERVAL_SECONDS,
        settings.MAX_PRS,
    )
    return task
