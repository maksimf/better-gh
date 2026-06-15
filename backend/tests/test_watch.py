"""Tests for server-side PR watch notifications."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from app import prefs, state
from app.model import PR, Checks
from app.watch import (
    NTFY_KEY,
    WATCHED_KEY,
    is_ready_to_notify,
    process_watches_after_poll,
    watch_key,
)


def _temp_db_path() -> str:
    d = tempfile.mkdtemp(prefix="better-gh-watch-")
    return str(Path(d) / "prefs.sqlite3")


def _pr(
    *,
    repo: str = "acme/widgets",
    number: int = 1,
    passed: int = 1,
    pending: int = 0,
    failed: int = 0,
    preview_url: str | None = "https://preview.example/x",
) -> PR:
    return PR(
        number=number,
        title="A PR",
        url=f"https://github.com/{repo}/pull/{number}",
        repo=repo,
        author="someone",
        is_draft=False,
        checks=Checks(passed=passed, pending=pending, failed=failed),
        comments_human=0,
        comments_bot=0,
        preview_url=preview_url,
        conflicts=0,
        updated_at="2026-05-20T10:00:00Z",
    )


class IsReadyToNotifyTests(unittest.TestCase):
    def test_green_checks_and_preview(self) -> None:
        self.assertTrue(is_ready_to_notify(_pr()))

    def test_requires_passed_check(self) -> None:
        self.assertFalse(is_ready_to_notify(_pr(passed=0)))

    def test_rejects_pending_or_failed(self) -> None:
        self.assertFalse(is_ready_to_notify(_pr(pending=1)))
        self.assertFalse(is_ready_to_notify(_pr(failed=1)))

    def test_requires_preview_url(self) -> None:
        self.assertFalse(is_ready_to_notify(_pr(preview_url=None)))


class ProcessWatchesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await prefs.close()
        await prefs.connect(_temp_db_path())
        await state.drop_user("alice")

    async def asyncTearDown(self) -> None:
        await state.drop_user("alice")
        await prefs.close()

    async def test_first_poll_seeds_without_notifying(self) -> None:
        key = watch_key("acme/widgets", 1)
        await prefs.set_many(
            "alice",
            {WATCHED_KEY: [key], NTFY_KEY: "my-topic"},
        )
        pr = _pr(pending=1)
        transport = httpx.MockTransport(lambda req: httpx.Response(500))
        async with httpx.AsyncClient(transport=transport) as client:
            await process_watches_after_poll("alice", [pr], client)

        stored = await prefs.get_all("alice")
        self.assertEqual(stored[WATCHED_KEY], [key])
        user = state.get("alice")
        assert user is not None
        self.assertFalse(user.watch_last_ready[key])

    async def test_ready_edge_notifies_and_unwatches(self) -> None:
        key = watch_key("acme/widgets", 1)
        await prefs.set_many(
            "alice",
            {WATCHED_KEY: [key], NTFY_KEY: "my-topic"},
        )
        user = await state.get_or_create("alice")
        user.watch_last_ready[key] = False

        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await process_watches_after_poll("alice", [_pr()], client)

        self.assertEqual(calls, ["/my-topic"])
        stored = await prefs.get_all("alice")
        self.assertNotIn(WATCHED_KEY, stored)
        self.assertNotIn(key, user.watch_last_ready)

    async def test_notify_failure_keeps_watch(self) -> None:
        key = watch_key("acme/widgets", 1)
        await prefs.set_many(
            "alice",
            {WATCHED_KEY: [key], NTFY_KEY: "my-topic"},
        )
        user = await state.get_or_create("alice")
        user.watch_last_ready[key] = False

        transport = httpx.MockTransport(lambda req: httpx.Response(500))
        async with httpx.AsyncClient(transport=transport) as client:
            await process_watches_after_poll("alice", [_pr()], client)

        stored = await prefs.get_all("alice")
        self.assertEqual(stored[WATCHED_KEY], [key])

    async def test_skips_when_no_channel(self) -> None:
        key = watch_key("acme/widgets", 1)
        await prefs.set_many("alice", {WATCHED_KEY: [key]})
        user = await state.get_or_create("alice")
        user.watch_last_ready[key] = False

        transport = httpx.MockTransport(
            mock.Mock(side_effect=AssertionError("should not call ntfy"))
        )
        async with httpx.AsyncClient(transport=transport) as client:
            await process_watches_after_poll("alice", [_pr()], client)

        stored = await prefs.get_all("alice")
        self.assertEqual(stored[WATCHED_KEY], [key])


if __name__ == "__main__":
    unittest.main()
