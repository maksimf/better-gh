"""In-memory snapshot store and SSE subscriber registry."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from .model import PR

log = logging.getLogger("better_gh.state")

_QUEUE_MAXSIZE = 16
_HEARTBEAT_INTERVAL_SECONDS = 15.0


@dataclass(frozen=True)
class Snapshot:
    """A point-in-time view of all tracked PRs."""

    prs: list[PR] = field(default_factory=list)

    @property
    def fingerprints(self) -> frozenset[tuple]:
        return frozenset(pr.fingerprint() for pr in self.prs)


_snapshot: Snapshot = Snapshot(prs=[])
_last_polled_at: datetime | None = None
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


def set_snapshot(new: Snapshot) -> bool:
    """Replace the current snapshot. Returns ``True`` iff the visible
    fingerprint set changed (subscribers should be notified)."""
    global _snapshot
    changed = new.fingerprints != _snapshot.fingerprints
    _snapshot = new
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


async def subscribe() -> AsyncIterator[dict[str, str]]:
    """Async generator that yields SSE events for one subscriber.

    Yields dicts shaped for ``sse-starlette.EventSourceResponse``::

        {"event": "prs",  "data": "<html>"}
        {"event": "meta", "data": "<html>"}
        {"event": "ping", "data": ""}

    Cleans the queue out of the subscriber set on cancellation.
    """
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    async with _subscribers_lock:
        _subscribers.add(queue)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}
                continue
            yield payload
    finally:
        async with _subscribers_lock:
            _subscribers.discard(queue)


def _flatten(html: str) -> str:
    """SSE data lines may not contain raw newlines; collapse them."""
    return html.replace("\r\n", "\n").replace("\n", "")
