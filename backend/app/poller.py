"""Per-user background poll loop that keeps each viewer's snapshot fresh.

Lifecycle is driven by a request keep-alive in :mod:`app.main`: the
``/api/dashboard`` handler calls :func:`start_poller_for` the first time
a viewer fetches and ``state.reap_idle`` (run from a global reaper)
cancels the task once the viewer stops fetching. No always-on background
loop; nothing runs for signed-out users.

The poller only fetches GitHub and stores the snapshot -- the React SPA
reads it back over ``/api/dashboard`` via react-query, so there's no
server-push / render step here anymore.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from . import state
from .config import settings
from .github import GitHubClient, GitHubRateLimitError

log = logging.getLogger("better_gh.poller")


async def poll_once(client: GitHubClient, *, login: str) -> bool:
    """Fetch PRs + incoming reviews for ``login`` and swap into their snapshot.

    Rate-limit failures are recorded as the viewer's error message (and
    re-raised so callers like ``/refresh`` can return a 502). The error
    persists until the previous error's ``reset_at`` actually expires --
    a single intermittent successful poll mid-window no longer flickers
    it away. Returns ``True`` when the viewer's PR list changed.
    """
    try:
        prs, reviews, rate_limit = await client.fetch_dashboard_snapshot()
    except GitHubRateLimitError as exc:
        await state.set_error(login, str(exc), exc.reset_at)
        log.warning("poll[%s]: rate limited (reset_at=%s)", login, exc.reset_at)
        raise

    new_snapshot = state.Snapshot(prs=prs, incoming_reviews=reviews)
    prs_changed, reviews_changed = await state.set_snapshot(login, new_snapshot)
    await state.mark_polled(login)

    # Only clear the error once the previous reset window has actually
    # expired. Mid-window successes (typical of GitHub's secondary
    # "anti-burst" limits) used to flicker the banner away before the
    # user could read it; now it persists until the limit truly lifts.
    prev_reset = state.error_reset_at(login)
    if prev_reset is None or prev_reset <= datetime.now(timezone.utc):
        await state.set_error(login, "", None)

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
    return prs_changed


async def poll_forever(
    client: GitHubClient,
    interval_seconds: int,
    *,
    login: str,
) -> None:
    """Loop forever for ``login``; never exits on its own. Cancellation stops it."""
    try:
        while True:
            try:
                await poll_once(client, login=login)
            except asyncio.CancelledError:
                log.info("poller[%s] cancelled; exiting loop", login)
                raise
            except GitHubRateLimitError as exc:
                # Already recorded as the viewer's error in poll_once;
                # keep the log line short so the loop doesn't spam stack
                # traces while we wait out the limit.
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
        # cleanly.
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
    http_client: httpx.AsyncClient,
) -> asyncio.Task:
    """Ensure a background poller is running for ``login``; idempotent.

    Returns the existing task if one is already alive for this viewer;
    otherwise spawns ``poll_forever`` against a fresh per-user
    :class:`GitHubClient`. Teardown is handled by ``state.reap_idle`` /
    ``state.drop_user``.
    """
    existing = state.get_poll_task(login)
    if existing is not None and not existing.done():
        return existing

    client = build_user_client(token, http_client=http_client)
    task = asyncio.create_task(
        poll_forever(
            client,
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
