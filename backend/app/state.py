"""Per-user in-memory snapshot store + poller lifecycle bookkeeping.

The whole "no database" trick on the runtime side: every signed-in
viewer gets their own :class:`UserState` in ``_states`` keyed by their
lower-cased GitHub login. Nothing persists across process restarts --
the first ``/api/dashboard`` request after a restart re-warms the
snapshot from a fresh poll.

The per-user poller task is tracked here. Its lifecycle is driven by a
request keep-alive: ``/api/dashboard`` calls :func:`touch` on every
fetch, and a global reaper (:func:`reap_idle`) cancels pollers whose
viewer hasn't fetched within the idle TTL. Signing out drops the user
immediately via :func:`drop_user`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from .model import PR, ReviewPR

log = logging.getLogger("better_gh.state")


@dataclass(frozen=True)
class Snapshot:
    """A point-in-time view of all tracked PRs for one viewer.

    ``prs`` holds the viewer's own (authored + assigned) open PRs that the
    main board renders. ``incoming_reviews`` holds open PRs where the
    viewer has been requested as a reviewer -- the "Reviewing" tab.
    """

    prs: list[PR] = field(default_factory=list)
    incoming_reviews: list[ReviewPR] = field(default_factory=list)

    @property
    def fingerprints(self) -> frozenset[tuple]:
        return frozenset(pr.fingerprint() for pr in self.prs)

    @property
    def review_fingerprints(self) -> frozenset[tuple]:
        return frozenset(pr.fingerprint() for pr in self.incoming_reviews)


@dataclass
class UserState:
    """Everything we keep in memory for a single signed-in viewer.

    All mutation should go through the module-level helpers
    (:func:`set_snapshot`, :func:`set_error`, ...) so the locking and
    the "did this change?" comparisons stay in one place.

    ``last_seen_at`` is stamped on every ``/api/dashboard`` fetch and
    drives the idle reaper -- a viewer whose tab is closed eventually
    gets reaped unless they still have watched PRs (see
    :func:`reap_idle`). ``watch_last_ready`` tracks the last-known
    readiness of each watched key so we only notify on edges.
    """

    snapshot: Snapshot = field(default_factory=Snapshot)
    last_polled_at: datetime | None = None
    last_seen_at: datetime | None = None
    error_message: str = ""
    error_reset_at: datetime | None = None
    poll_task: asyncio.Task | None = None
    github_token: str | None = None
    watch_last_ready: dict[str, bool] = field(default_factory=dict)


_states: dict[str, UserState] = {}
_lock = asyncio.Lock()


def _key(login: str) -> str:
    return (login or "").lower()


async def _get_or_create_locked(login: str) -> UserState:
    """Caller must already hold ``_lock``."""
    key = _key(login)
    state = _states.get(key)
    if state is None:
        state = UserState()
        _states[key] = state
    return state


async def get_or_create(login: str) -> UserState:
    """Public counterpart that takes the lock itself."""
    async with _lock:
        return await _get_or_create_locked(login)


def get(login: str) -> UserState | None:
    """Cheap lock-free read used by render-time helpers.

    Safe enough because callers don't mutate; readers just see a
    consistent-ish view of whichever ``UserState`` is currently live.
    """
    return _states.get(_key(login))


def current_snapshot(login: str) -> Snapshot:
    state = get(login)
    return state.snapshot if state is not None else Snapshot()


def last_polled_at(login: str) -> datetime | None:
    state = get(login)
    return state.last_polled_at if state is not None else None


def current_error(login: str) -> str:
    state = get(login)
    return state.error_message if state is not None else ""


def error_reset_at(login: str) -> datetime | None:
    state = get(login)
    return state.error_reset_at if state is not None else None


async def mark_polled(login: str) -> datetime:
    """Stamp ``now`` on the viewer's state and return it."""
    state = await get_or_create(login)
    now = datetime.now(timezone.utc)
    state.last_polled_at = now
    return now


async def remember_token(login: str, token: str) -> None:
    """Store the viewer's GitHub token for poller (re)starts."""
    user = await get_or_create(login)
    user.github_token = token


async def touch(login: str) -> None:
    """Mark the viewer as recently active (keep their poller alive)."""
    state = await get_or_create(login)
    state.last_seen_at = datetime.now(timezone.utc)


async def set_snapshot(login: str, new: Snapshot) -> tuple[bool, bool]:
    """Replace the viewer's snapshot.

    Returns ``(prs_changed, reviews_changed)`` -- still handy for the
    poller's log line even though there's no SSE broadcast anymore.
    """
    state = await get_or_create(login)
    prs_changed = new.fingerprints != state.snapshot.fingerprints
    reviews_changed = new.review_fingerprints != state.snapshot.review_fingerprints
    state.snapshot = new
    return prs_changed, reviews_changed


async def set_error(
    login: str, message: str, reset_at: datetime | None = None
) -> bool:
    """Replace the viewer's error message + its reset deadline.

    Returns ``True`` iff the message actually changed. ``reset_at`` is
    stored even when the message is unchanged so a fresher rate-limit
    hit can push the deadline back.
    """
    state = await get_or_create(login)
    changed = message != state.error_message
    state.error_message = message
    state.error_reset_at = reset_at
    return changed


def set_poll_task(login: str, task: asyncio.Task | None) -> None:
    """Record (or clear) the poller task bound to this viewer."""
    state = get(login)
    if state is None:
        return
    state.poll_task = task


def get_poll_task(login: str) -> asyncio.Task | None:
    state = get(login)
    return state.poll_task if state is not None else None


async def drop_user(login: str) -> bool:
    """Cancel ``login``'s poller and forget their state. Idempotent.

    Returns ``True`` when the user's state was actually removed. Used
    on sign-out and by the idle reaper.
    """
    key = _key(login)
    async with _lock:
        state = _states.get(key)
        if state is None:
            return False
        task = state.poll_task
        state.poll_task = None
        del _states[key]
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    log.info("dropped user state for %s", key)
    return True


async def reap_idle(ttl_seconds: float) -> int:
    """Drop every viewer whose last fetch is older than ``ttl_seconds``.

    Viewers with active watched PRs are kept alive so the backend poller
    can keep checking readiness after the browser tab closes.

    Returns the number of users reaped. Run periodically from a global
    background task started in the app lifespan.
    """
    from .watch import has_active_watches

    now = datetime.now(timezone.utc)
    async with _lock:
        candidates = [
            key
            for key, st in _states.items()
            if st.last_seen_at is not None
            and (now - st.last_seen_at).total_seconds() > ttl_seconds
        ]
    dropped = 0
    for key in candidates:
        if await has_active_watches(key):
            continue
        if await drop_user(key):
            dropped += 1
    return dropped


async def shutdown() -> None:
    """Cancel every poller and drop every user state. Called from lifespan."""
    async with _lock:
        tasks = [s.poll_task for s in _states.values() if s.poll_task is not None]
        _states.clear()
    for task in tasks:
        if not task.done():
            task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@asynccontextmanager
async def reaper(ttl_seconds: float, interval_seconds: float) -> AsyncIterator[None]:
    """Run the idle reaper for the duration of the ``async with`` block."""

    async def _loop() -> None:
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await reap_idle(ttl_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("idle reaper iteration failed")

    task = asyncio.create_task(_loop(), name="better-gh.reaper")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
