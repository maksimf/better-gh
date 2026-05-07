"""Background poll loop that keeps the in-memory snapshot fresh."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from . import state
from .github import GitHubClient, GitHubRateLimitError
from .model import PR
from .render import render_error_banner, render_meta

log = logging.getLogger("better_gh.poller")

RenderFn = Callable[[list[PR]], str]


async def poll_once(client: GitHubClient, render: RenderFn) -> bool:
    """Fetch PRs, swap into the snapshot, broadcast updates.

    Always broadcasts a ``meta`` event (so the "last updated" footer ticks
    on every successful poll) and a ``prs`` event when the snapshot's
    fingerprint set actually changed. Returns ``True`` when the PR fragment
    was re-broadcast.

    Rate-limit failures are surfaced as an ``error`` SSE event (and the
    exception is re-raised so callers like ``/refresh`` can return a 502).
    A successful poll clears any active error banner.
    """
    try:
        prs = await client.fetch_open_prs()
    except GitHubRateLimitError as exc:
        html = render_error_banner(str(exc), exc.reset_at)
        if state.set_error(html):
            await state.broadcast("error", html)
        log.warning("poll: rate limited (reset_at=%s)", exc.reset_at)
        raise

    new_snapshot = state.Snapshot(prs=prs)
    changed = state.set_snapshot(new_snapshot)
    polled_at = state.mark_polled()
    if state.set_error(""):
        await state.broadcast("error", "")
    if changed:
        html = render(prs)
        await state.broadcast("prs", html)
        log.info("poll: %d PRs (changed; broadcast sent)", len(prs))
    else:
        log.info("poll: %d PRs (unchanged)", len(prs))
    await state.broadcast("meta", render_meta(polled_at))
    return changed


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
