"""Per-user in-memory snapshot store + SSE subscriber registry.

The whole "no database" trick on the runtime side: every signed-in
viewer gets their own :class:`UserState` in ``_states`` keyed by their
lower-cased GitHub login. Nothing persists across process restarts --
SSE bootstrap on reconnect re-renders the snapshot from a fresh poll.

The per-user poller task is also tracked here so the lifecycle ties
neatly to subscriber refcount: the ``/events`` handler starts a poller
the first time a user connects and asks us to drop the user when the
last subscriber disconnects (which cancels the task).
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

_QUEUE_MAXSIZE = 16
_HEARTBEAT_INTERVAL_SECONDS = 15.0


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
    (:func:`set_snapshot`, :func:`set_error`, :func:`broadcast`, ...)
    so the locking and the "did this change?" comparisons stay in one
    place. The fields are public-ish for ergonomics (read access from
    routes), but writes from outside this module will skip the
    bookkeeping.

    ``reviewer_login`` is the GitHub login this viewer chose to track
    in the per-card "R" chip / "Request review" button / APPROVED
    column rule. Cached here so the SSE broadcast path (which has no
    Request) can read it without re-parsing the cookie. ``None`` means
    "fall back to ``settings.REVIEWER_LOGIN``"; empty string means "no
    reviewer, hide the chip entirely".
    """

    snapshot: Snapshot = field(default_factory=Snapshot)
    last_polled_at: datetime | None = None
    error_html: str = ""
    error_reset_at: datetime | None = None
    subscribers: set[asyncio.Queue[dict[str, str]]] = field(default_factory=set)
    poll_task: asyncio.Task | None = None
    reviewer_login: str | None = None


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
    return state.error_html if state is not None else ""


def error_reset_at(login: str) -> datetime | None:
    state = get(login)
    return state.error_reset_at if state is not None else None


async def mark_polled(login: str) -> datetime:
    """Stamp ``now`` on the viewer's state and return it."""
    state = await get_or_create(login)
    now = datetime.now(timezone.utc)
    state.last_polled_at = now
    return now


async def set_snapshot(login: str, new: Snapshot) -> tuple[bool, bool]:
    """Replace the viewer's snapshot.

    Returns ``(prs_changed, reviews_changed)`` so the poller can decide
    which SSE events to broadcast independently.
    """
    state = await get_or_create(login)
    prs_changed = new.fingerprints != state.snapshot.fingerprints
    reviews_changed = new.review_fingerprints != state.snapshot.review_fingerprints
    state.snapshot = new
    return prs_changed, reviews_changed


async def set_error(
    login: str, html: str, reset_at: datetime | None = None
) -> bool:
    """Replace the viewer's error-banner HTML + its reset deadline.

    Returns ``True`` iff the HTML actually changed (callers broadcast
    on ``True`` only). ``reset_at`` is stored even when the HTML is
    unchanged so a fresher rate-limit hit can push the deadline back.
    """
    state = await get_or_create(login)
    changed = html != state.error_html
    state.error_html = html
    state.error_reset_at = reset_at
    return changed


async def broadcast(login: str, event: str, data: str) -> None:
    """Push an SSE payload to every subscriber for ``login``. Drops on a full queue."""
    state = get(login)
    if state is None:
        return
    payload = {"event": event, "data": _flatten(data)}
    async with _lock:
        targets = list(state.subscribers)
    for queue in targets:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            log.warning("SSE subscriber queue full; dropping update for %s", login)


async def set_reviewer(login: str, reviewer: str | None) -> tuple[bool, str | None]:
    """Update the viewer's tracked reviewer login.

    ``reviewer`` may be ``None`` (revert to global default) or a
    non-empty trimmed string (track that login). Empty strings are
    normalised to ``""`` -- meaning "explicitly no reviewer" -- so the
    chip stays hidden even when ``settings.REVIEWER_LOGIN`` is set.

    Returns ``(changed, normalised_value)``: callers should
    re-render + re-broadcast only when ``changed`` is ``True``.
    """
    if reviewer is None:
        normalised: str | None = None
    else:
        normalised = reviewer.strip()
    state = await get_or_create(login)
    changed = state.reviewer_login != normalised
    state.reviewer_login = normalised
    return changed, normalised


def get_reviewer(login: str) -> str | None:
    """Read the viewer's cached reviewer login. ``None`` if unset."""
    state = get(login)
    return state.reviewer_login if state is not None else None


def set_poll_task(login: str, task: asyncio.Task | None) -> None:
    """Record (or clear) the poller task bound to this viewer.

    Lock-free on purpose -- only the ``/events`` handler and
    ``drop_if_idle`` ever touch this, and both run on the event loop
    in deterministic order around `get_or_create` / subscriber
    bookkeeping calls.
    """
    state = get(login)
    if state is None:
        return
    state.poll_task = task


def get_poll_task(login: str) -> asyncio.Task | None:
    state = get(login)
    return state.poll_task if state is not None else None


@asynccontextmanager
async def subscriber(login: str) -> AsyncIterator[asyncio.Queue[dict[str, str]]]:
    """Register an SSE subscriber queue for the lifetime of the ``async with``.

    Callers register *before* yielding any bootstrap events so a
    broadcast that fires during the bootstrap window lands on the
    queue (rather than being dropped because no one was listening
    yet). On exit we always remove the queue; ``drop_if_idle`` is the
    caller's responsibility (the ``/events`` handler invokes it after
    the ``async with`` returns so the poller can be cancelled).
    """
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    async with _lock:
        state = await _get_or_create_locked(login)
        state.subscribers.add(queue)
    try:
        yield queue
    finally:
        async with _lock:
            state = _states.get(_key(login))
            if state is not None:
                state.subscribers.discard(queue)


async def subscriber_count(login: str) -> int:
    state = get(login)
    if state is None:
        return 0
    async with _lock:
        return len(state.subscribers)


async def drop_if_idle(login: str) -> bool:
    """If no one's listening for ``login``, cancel their poller and forget them.

    Returns ``True`` when the user's state was actually removed.
    Idempotent and safe to call after every subscriber disconnect --
    re-connections trigger ``get_or_create`` + ``start_poller_for``
    fresh.
    """
    key = _key(login)
    async with _lock:
        state = _states.get(key)
        if state is None:
            return False
        if state.subscribers:
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
    log.info("dropped idle user state for %s", key)
    return True


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


HEARTBEAT_INTERVAL_SECONDS = _HEARTBEAT_INTERVAL_SECONDS


def _flatten(html: str) -> str:
    """SSE data lines may not contain raw newlines; collapse them."""
    return html.replace("\r\n", "\n").replace("\n", "")
