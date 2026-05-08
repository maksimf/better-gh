"""In-memory snapshot store and SSE subscriber registry."""
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
    """A point-in-time view of all tracked PRs.

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


_snapshot: Snapshot = Snapshot(prs=[], incoming_reviews=[])
_last_polled_at: datetime | None = None
_error_html: str = ""
_error_reset_at: datetime | None = None
_subscribers: set[asyncio.Queue[dict[str, str]]] = set()
_subscribers_lock = asyncio.Lock()


def current_snapshot() -> Snapshot:
    return _snapshot


def last_polled_at() -> datetime | None:
    return _last_polled_at


def mark_polled() -> datetime:
    """Record the timestamp of a successful poll and return it."""
    global _last_polled_at
    _last_polled_at = datetime.now(timezone.utc)
    return _last_polled_at


def set_snapshot(new: Snapshot) -> tuple[bool, bool]:
    """Replace the current snapshot.

    Returns ``(prs_changed, reviews_changed)`` so the caller can decide
    which SSE events to broadcast independently.
    """
    global _snapshot
    prs_changed = new.fingerprints != _snapshot.fingerprints
    reviews_changed = new.review_fingerprints != _snapshot.review_fingerprints
    _snapshot = new
    return prs_changed, reviews_changed


def current_error() -> str:
    """The current error-banner HTML, or empty string if no active error."""
    return _error_html


def error_reset_at() -> datetime | None:
    """Reset timestamp recorded alongside the active error, if any.

    The poller uses this to keep the banner visible until the rate limit
    window has actually expired. Returns ``None`` when there's no active
    error or when the upstream didn't tell us when the limit resets.
    """
    return _error_reset_at


def set_error(html: str, reset_at: datetime | None = None) -> bool:
    """Replace the current error-banner HTML + its reset deadline.

    Returns ``True`` iff the HTML actually changed (callers broadcast on
    ``True`` only). ``reset_at`` is stored even when the HTML is unchanged
    so callers can refresh the deadline if a new rate-limit hit gives us a
    later reset (rare but defensible)."""
    global _error_html, _error_reset_at
    changed = html != _error_html
    _error_html = html
    _error_reset_at = reset_at
    return changed


async def broadcast(event: str, data: str) -> None:
    """Push an SSE payload to every subscriber. Drops on a full queue."""
    payload = {"event": event, "data": _flatten(data)}
    async with _subscribers_lock:
        targets = list(_subscribers)
    for queue in targets:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            log.warning("SSE subscriber queue full; dropping update")


@asynccontextmanager
async def subscriber() -> AsyncIterator[asyncio.Queue[dict[str, str]]]:
    """Register an SSE subscriber queue for the lifetime of the ``async with``.

    Callers register *before* yielding any bootstrap events so a broadcast
    that fires during the bootstrap window lands on the queue (rather than
    being dropped because no one was listening yet)::

        async with state.subscriber() as queue:
            yield bootstrap_event
            ...
            payload = await queue.get()

    The queue is removed on exit (cancellation, exception, or normal close).
    """
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    async with _subscribers_lock:
        _subscribers.add(queue)
    try:
        yield queue
    finally:
        async with _subscribers_lock:
            _subscribers.discard(queue)


async def subscribe() -> AsyncIterator[dict[str, str]]:
    """Async generator that yields SSE events for one subscriber.

    Kept for callers that want a self-contained generator (no bootstrap
    events). New code that needs to mix bootstrap + live events should
    use :func:`subscriber` so the queue is registered up-front.
    """
    async with subscriber() as queue:
        while True:
            try:
                payload = await asyncio.wait_for(
                    queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue
            yield payload


HEARTBEAT_INTERVAL_SECONDS = _HEARTBEAT_INTERVAL_SECONDS


def _flatten(html: str) -> str:
    """SSE data lines may not contain raw newlines; collapse them."""
    return html.replace("\r\n", "\n").replace("\n", "")
