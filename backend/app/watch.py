"""Server-side PR watch notifications via ntfy.sh.

Watched PR keys live in the synced prefs store (``better-gh.watched``).
After each successful GitHub poll the poller evaluates watched PRs; when
one transitions into the ready state (checks green + preview URL) we
publish an ntfy notification and remove it from the watch list.

Seeding on first sight (or when a key is newly added via ``PUT
/api/prefs``) ensures toggling Watch on an already-ready PR does not
fire immediately — only a not-ready → ready edge notifies.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from . import prefs, state
from .model import PR

log = logging.getLogger("better_gh.watch")

WATCHED_KEY = "better-gh.watched"
NTFY_KEY = "better-gh.ntfy-channel"


def watch_key(repo: str, number: int) -> str:
    return f"{repo}#{number}"


def is_ready_to_notify(pr: PR) -> bool:
    """Ready for a watch ping: all checks green and a preview URL exists."""
    c = pr.checks
    checks_green = c.passed > 0 and c.pending == 0 and c.failed == 0
    return checks_green and pr.preview_url is not None


def _watched_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


async def has_active_watches(login: str) -> bool:
    """True when the viewer has at least one PR on their watch list."""
    stored = await prefs.get_all(login)
    return len(_watched_list(stored.get(WATCHED_KEY))) > 0


async def seed_watch(login: str, key: str, *, ready: bool) -> None:
    user = await state.get_or_create(login)
    user.watch_last_ready[key] = ready


async def clear_watch_seeds(login: str) -> None:
    user = await state.get_or_create(login)
    user.watch_last_ready.clear()


async def seed_newly_watched(
    login: str, *, added: set[str], prs: list[PR]
) -> None:
    """Seed readiness state for keys just added to the watch list."""
    by_key = {watch_key(p.repo, p.number): p for p in prs}
    for key in added:
        pr = by_key.get(key)
        await seed_watch(login, key, ready=is_ready_to_notify(pr) if pr else False)


async def unwatch(login: str, key: str) -> None:
    """Remove one key from the persisted watch list."""
    stored = await prefs.get_all(login)
    current = _watched_list(stored.get(WATCHED_KEY))
    next_list = [k for k in current if k != key]
    if next_list:
        await prefs.set_many(login, {WATCHED_KEY: next_list})
    else:
        await prefs.set_many(login, {WATCHED_KEY: None})
    user = state.get(login)
    if user is not None:
        user.watch_last_ready.pop(key, None)


async def notify_ready(
    http_client: httpx.AsyncClient, pr: PR, channel: str
) -> bool:
    """POST a ready notification to ntfy.sh. Returns True on success."""
    topic = quote(channel, safe="")
    try:
        resp = await http_client.post(
            f"https://ntfy.sh/{topic}",
            content=(
                f"{pr.repo}\n{pr.title}\nChecks passed \u00b7 preview ready"
            ),
            headers={
                "Title": f"Ready - #{pr.number}",
                "Click": pr.url,
                "Tags": "white_check_mark",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return True
    except Exception:
        log.exception(
            "ntfy notify failed for %s (channel=%s)", watch_key(pr.repo, pr.number), channel
        )
        return False


async def process_watches_after_poll(
    login: str, prs: list[PR], http_client: httpx.AsyncClient
) -> None:
    """Evaluate watched PRs after a snapshot refresh; notify + unwatch on ready."""
    stored = await prefs.get_all(login)
    watched = _watched_list(stored.get(WATCHED_KEY))
    if not watched:
        await clear_watch_seeds(login)
        return

    channel_raw = stored.get(NTFY_KEY)
    channel = channel_raw.strip() if isinstance(channel_raw, str) else ""
    if not channel:
        return

    user = await state.get_or_create(login)
    by_key = {watch_key(p.repo, p.number): p for p in prs}
    seen: set[str] = set()

    for key in watched:
        seen.add(key)
        pr = by_key.get(key)
        if pr is None:
            continue

        ready = is_ready_to_notify(pr)
        prev = user.watch_last_ready.get(key)

        if prev is None:
            user.watch_last_ready[key] = ready
            continue

        if ready and not prev:
            if await notify_ready(http_client, pr, channel):
                await unwatch(login, key)
                seen.discard(key)
            else:
                user.watch_last_ready[key] = ready
        else:
            user.watch_last_ready[key] = ready

    for key in list(user.watch_last_ready.keys()):
        if key not in seen:
            user.watch_last_ready.pop(key, None)
