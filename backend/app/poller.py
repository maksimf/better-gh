"""Background poll loop that keeps the in-memory snapshot fresh."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from . import state
from .github import GitHubClient
from .model import PR
from .render import render_meta

log = logging.getLogger("better_gh.poller")

RenderFn = Callable[[list[PR]], str]


async def poll_once(client: GitHubClient, render: RenderFn) -> bool:
    """Fetch PRs, swap into the snapshot, broadcast updates.

    Always broadcasts a ``meta`` event (so the "last updated" footer ticks
    on every successful poll) and a ``prs`` event when the snapshot's
    fingerprint set actually changed. Returns ``True`` when the PR fragment
    was re-broadcast.
    """
    prs = await client.fetch_open_prs()
    new_snapshot = state.Snapshot(prs=prs)
    changed = state.set_snapshot(new_snapshot)
    polled_at = state.mark_polled()
    if changed:
        html = render(prs)
        await state.broadcast("prs", html)
        log.info("snapshot changed (%d PRs); broadcast sent", len(prs))
    else:
        log.debug("snapshot unchanged (%d PRs)", len(prs))
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
        except Exception:
            log.exception("poll failed")
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            log.info("poller cancelled during sleep; exiting loop")
            raise
