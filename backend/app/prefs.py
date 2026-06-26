"""Durable per-user preference storage, backed by SQLite.

The runtime side of the app is still "no database" -- PR snapshots live
in process memory in :mod:`state`. This module is the one deliberate
exception: it persists the handful of per-viewer preferences that used
to live only in the browser's ``localStorage`` so they sync across a
user's devices.

Rows are keyed by ``(login, key)`` where ``login`` is the lower-cased
GitHub login already verified on every request via the signed session
cookie (see :mod:`app.auth`). Values are JSON-encoded blobs. A small
whitelist of allowed keys plus a per-value size cap keep the table
bounded -- the API only ever stores the known preference keys.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

log = logging.getLogger("better_gh.prefs")

# The exhaustive set of preference keys the client is allowed to sync.
# Mirrors the ``better-gh.*`` localStorage keys on the frontend. Anything
# outside this set is rejected so the table can't grow unboundedly.
ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "better-gh.manually-reviewed",
        "better-gh.deferred",
        "better-gh.watched",
        "better-gh.selected-repos",
        "better-gh.reviewer-login",
        "better-gh.theme",
        "better-gh.cloud-agents",
        "better-gh.ntfy-channel",
        "better-gh.pr-notes",
    }
)

# Cap on a single JSON-encoded value. 64 KB is comfortably more than the
# largest realistic preference (a few hundred "owner/repo#number" keys).
MAX_VALUE_BYTES = 64 * 1024

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prefs (
    login      TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (login, key)
)
"""

_conn: aiosqlite.Connection | None = None


class PrefError(ValueError):
    """Raised when a preference write is rejected (bad key / oversized)."""


async def connect(path: str) -> None:
    """Open the SQLite connection and ensure the schema exists.

    Called once from the app lifespan. The parent directory is created
    if missing so a fresh deploy with an empty mounted volume just works.
    ``:memory:`` is honoured as-is (handy for tests).
    """
    global _conn
    if _conn is not None:
        return
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(path)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute(_CREATE_TABLE_SQL)
    await _conn.commit()
    log.info("prefs store ready at %s", path)


async def close() -> None:
    """Close the connection. Idempotent; called from the lifespan finally."""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def _require_conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("prefs store not connected; call connect() first.")
    return _conn


def _validate(key: str, encoded: str) -> None:
    if key not in ALLOWED_KEYS:
        raise PrefError(f"Unknown preference key: {key!r}")
    if len(encoded.encode("utf-8")) > MAX_VALUE_BYTES:
        raise PrefError(f"Preference {key!r} exceeds {MAX_VALUE_BYTES} bytes")


async def get_all(login: str) -> dict[str, Any]:
    """Return all stored preferences for ``login`` as a JSON-decoded dict.

    A value that somehow failed to decode is skipped rather than blowing
    up the whole fetch.
    """
    conn = _require_conn()
    async with conn.execute(
        "SELECT key, value FROM prefs WHERE login = ?", (login.lower(),)
    ) as cursor:
        rows = await cursor.fetchall()
    out: dict[str, Any] = {}
    for row in rows:
        try:
            out[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            log.warning("dropping un-decodable pref %s for %s", row["key"], login)
    return out


async def set_many(login: str, values: dict[str, Any]) -> dict[str, Any]:
    """Upsert each ``key -> value`` for ``login``. Returns the stored dict.

    A ``None`` value deletes the key instead of storing it (used when the
    client clears a preference, e.g. resetting the tracked reviewer back
    to "unconfigured"). Validates every non-null key against
    :data:`ALLOWED_KEYS` and the size cap *before* writing anything, so a
    bad key in the batch rejects the whole request rather than leaving a
    partial write.
    """
    encoded: dict[str, str] = {}
    deletes: list[str] = []
    for key, value in values.items():
        if key not in ALLOWED_KEYS:
            raise PrefError(f"Unknown preference key: {key!r}")
        if value is None:
            deletes.append(key)
            continue
        blob = json.dumps(value, separators=(",", ":"))
        _validate(key, blob)
        encoded[key] = blob

    conn = _require_conn()
    now = datetime.now(timezone.utc).isoformat()
    key_lc = login.lower()
    if encoded:
        await conn.executemany(
            """
            INSERT INTO prefs (login, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(login, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            [(key_lc, key, blob, now) for key, blob in encoded.items()],
        )
    if deletes:
        await conn.executemany(
            "DELETE FROM prefs WHERE login = ? AND key = ?",
            [(key_lc, key) for key in deletes],
        )
    await conn.commit()
    return {key: values[key] for key in encoded}
