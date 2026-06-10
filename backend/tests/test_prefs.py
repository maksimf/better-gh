"""Tests for the SQLite-backed per-user preference store + its routes.

Covers the unit-level promises of :mod:`app.prefs` (round-trip,
per-user isolation, null-deletes, key whitelist, size cap) and the
integration-level promises of the ``/api/prefs`` routes (auth gating,
GET/PUT round-trip, 400 on a bad key).
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import prefs
from app.config import settings


def _temp_db_path() -> str:
    d = tempfile.mkdtemp(prefix="better-gh-prefs-")
    return str(Path(d) / "prefs.sqlite3")


class PrefStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await prefs.close()  # ensure no stale module-global connection
        await prefs.connect(_temp_db_path())

    async def asyncTearDown(self) -> None:
        await prefs.close()

    async def test_set_and_get_round_trip(self) -> None:
        await prefs.set_many(
            "maksimf",
            {
                "better-gh.watched": ["acme/widgets#1", "acme/widgets#2"],
                "better-gh.theme": "dark",
            },
        )
        got = await prefs.get_all("maksimf")
        self.assertEqual(
            got,
            {
                "better-gh.watched": ["acme/widgets#1", "acme/widgets#2"],
                "better-gh.theme": "dark",
            },
        )

    async def test_login_is_case_insensitive(self) -> None:
        await prefs.set_many("MaksimF", {"better-gh.theme": "dark"})
        got = await prefs.get_all("maksimf")
        self.assertEqual(got, {"better-gh.theme": "dark"})

    async def test_upsert_overwrites_existing_value(self) -> None:
        await prefs.set_many("u", {"better-gh.theme": "light"})
        await prefs.set_many("u", {"better-gh.theme": "dark"})
        got = await prefs.get_all("u")
        self.assertEqual(got["better-gh.theme"], "dark")

    async def test_users_are_isolated(self) -> None:
        await prefs.set_many("alice", {"better-gh.theme": "dark"})
        await prefs.set_many("bob", {"better-gh.theme": "light"})
        self.assertEqual((await prefs.get_all("alice"))["better-gh.theme"], "dark")
        self.assertEqual((await prefs.get_all("bob"))["better-gh.theme"], "light")

    async def test_null_value_deletes_key(self) -> None:
        await prefs.set_many("u", {"better-gh.reviewer-login": "nicoraga1"})
        await prefs.set_many("u", {"better-gh.reviewer-login": None})
        self.assertEqual(await prefs.get_all("u"), {})

    async def test_unknown_key_rejected(self) -> None:
        with self.assertRaises(prefs.PrefError):
            await prefs.set_many("u", {"better-gh.evil": "x"})

    async def test_partial_batch_with_bad_key_writes_nothing(self) -> None:
        with self.assertRaises(prefs.PrefError):
            await prefs.set_many(
                "u",
                {"better-gh.theme": "dark", "not-allowed": "x"},
            )
        self.assertEqual(await prefs.get_all("u"), {})

    async def test_oversized_value_rejected(self) -> None:
        huge = ["x" * 1000] * 1000  # well past the 64 KB cap once encoded
        with self.assertRaises(prefs.PrefError):
            await prefs.set_many("u", {"better-gh.watched": huge})


_TEST_SECRET = "test-session-secret-do-not-use-in-prod"


class PrefRouteTests(unittest.TestCase):
    """Exercise GET/PUT /api/prefs through the real app + lifespan."""

    @classmethod
    def setUpClass(cls) -> None:
        # Make sure no store-level test left a connection open; the app
        # lifespan opens its own against the temp path below.
        asyncio.run(prefs.close())
        cls._patch = mock.patch.multiple(
            settings,
            SESSION_SECRET=_TEST_SECRET,
            COOKIE_SECURE=False,
            PREFS_DB_PATH=_temp_db_path(),
        )
        cls._patch.start()
        from app import main as main_module

        cls._main_module = main_module
        # ``with`` triggers the lifespan so prefs.connect() runs.
        cls._client_cm = TestClient(main_module.app)
        cls._client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_cm.__exit__(None, None, None)
        cls._patch.stop()

    def _signed_cookie(self, login: str = "maksimf", token: str = "tok") -> str:
        from app import auth

        return auth._session_serializer().dumps({"token": token, "login": login})

    def _auth(self, login: str = "maksimf") -> None:
        self._client.cookies.set("gh_session", self._signed_cookie(login))

    def test_prefs_require_auth(self) -> None:
        self._client.cookies.clear()
        self.assertEqual(self._client.get("/api/prefs").status_code, 401)
        self.assertEqual(
            self._client.put("/api/prefs", json={"better-gh.theme": "dark"}).status_code,
            401,
        )

    def test_put_then_get_round_trip(self) -> None:
        try:
            self._auth("routeuser")
            put = self._client.put(
                "/api/prefs",
                json={"better-gh.theme": "dark", "better-gh.watched": ["a/b#1"]},
            )
            self.assertEqual(put.status_code, 200)
            got = self._client.get("/api/prefs")
        finally:
            self._client.cookies.clear()
        self.assertEqual(got.status_code, 200)
        self.assertEqual(
            got.json(),
            {"better-gh.theme": "dark", "better-gh.watched": ["a/b#1"]},
        )

    def test_put_unknown_key_returns_400(self) -> None:
        try:
            self._auth("routeuser2")
            r = self._client.put("/api/prefs", json={"better-gh.bogus": "x"})
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 400)

    def test_null_value_deletes_via_route(self) -> None:
        try:
            self._auth("routeuser3")
            self._client.put("/api/prefs", json={"better-gh.reviewer-login": "x"})
            self._client.put("/api/prefs", json={"better-gh.reviewer-login": None})
            got = self._client.get("/api/prefs")
        finally:
            self._client.cookies.clear()
        self.assertEqual(got.json(), {})


if __name__ == "__main__":
    unittest.main()
