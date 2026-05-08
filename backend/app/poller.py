"""Background poll loop that keeps the in-memory snapshot fresh."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from . import state
from .github import GitHubClient, GitHubRateLimitError
from .model import PR
from .render import render_error_banner, render_meta, render_reviews

log = logging.getLogger("better_gh.poller")

RenderFn = Callable[[list[PR]], str]


async def poll_once(client: GitHubClient, render: RenderFn) -> bool:
    """Fetch PRs + incoming reviews, swap into the snapshot, broadcast.

    Always broadcasts a ``meta`` event (so the "last updated" footer ticks
    on every successful poll). Broadcasts ``prs`` when the user's PRs
    changed and ``reviews`` when the incoming-reviews list changed --
    either independently. Returns ``True`` when the user's PR fragment
    was re-broadcast (kept for backwards-compat with callers that gate on
    that signal; the reviews update is fire-and-forget over SSE).

    Rate-limit failures are surfaced as an ``error`` SSE event (and the
    exception is re-raised so callers like ``/refresh`` can return a 502).
    The banner persists until the previous error's ``reset_at`` actually
    expires -- a single intermittent successful poll mid-window no longer
    flickers it away.
    """
    try:
        prs, reviews, rate_limit = await client.fetch_dashboard_snapshot()
    except GitHubRateLimitError as exc:
        html = render_error_banner(str(exc), exc.reset_at)
        if state.set_error(html, exc.reset_at):
            # ``gh-error`` (not ``error``) -- EventSource's native error
            # event collides with a custom event named "error" and
            # crashes the htmx SSE extension on reconnect attempts.
            await state.broadcast("gh-error", html)
        log.warning("poll: rate limited (reset_at=%s)", exc.reset_at)
        raise

    new_snapshot = state.Snapshot(prs=prs, incoming_reviews=reviews)
    prs_changed, reviews_changed = state.set_snapshot(new_snapshot)
    polled_at = state.mark_polled()

    # Only clear the error banner once the previous reset window has
    # actually expired. Mid-window successes (typical of GitHub's
    # secondary "anti-burst" limits) used to flicker the banner away
    # before the user could read it; now it persists until the limit
    # truly lifts.
    prev_reset = state.error_reset_at()
    if prev_reset is None or prev_reset <= datetime.now(timezone.utc):
        if state.set_error(""):
            await state.broadcast("gh-error", "")

    if prs_changed:
        await state.broadcast("prs", render(prs))
    if reviews_changed:
        await state.broadcast("reviews", render_reviews(reviews))
    log.info(
        "poll: %d PRs (%s), %d reviews (%s)",
        len(prs),
        "changed" if prs_changed else "unchanged",
        len(reviews),
        "changed" if reviews_changed else "unchanged",
    )
    if rate_limit is not None:
        log.info(
            "poll: rateLimit cost=%s remaining=%s/%s reset=%s",
            rate_limit.get("cost"),
            rate_limit.get("remaining"),
            rate_limit.get("limit"),
            rate_limit.get("resetAt"),
        )
    await state.broadcast("meta", render_meta(polled_at))
    return prs_changed


async def poll_forever(
    client: GitHubClient, render: RenderFn, interval_seconds: int
) -> None:
    """Loop forever; never exits on its own. Cancellation stops it."""
    while True:
        try:
            await poll_once(client, render)
        except asyncio.CancelledError:
            log.info("poller cancelled; exiting loop")
            raise
        except GitHubRateLimitError as exc:
            # Already broadcast as an error banner in poll_once; keep the
            # log line short so the loop doesn't spam stack traces while
            # we wait out the limit.
            log.warning("poll skipped: rate limited (reset_at=%s)", exc.reset_at)
        except Exception:
            log.exception("poll failed")
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            log.info("poller cancelled during sleep; exiting loop")
            raise
