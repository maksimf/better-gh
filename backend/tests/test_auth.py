"""Tests for the OAuth + signed-cookie session layer.

Covers the unit-level promises of :mod:`app.auth` (cookie roundtrip,
expiry, tampering, OAuth state CSRF) plus the integration-level
promises of :mod:`app.main` route gating (302 vs 401 depending on
whether a route is HTML- or API-shaped).
"""
from __future__ import annotations

import time
import unittest
from typing import Any
from unittest import mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app import auth
from app.config import settings


_TEST_SECRET = "test-session-secret-do-not-use-in-prod"


def _patched_settings():
    """Context manager that fills in the auth-related env vars for one test."""
    return mock.patch.multiple(
        settings,
        SESSION_SECRET=_TEST_SECRET,
        GITHUB_OAUTH_CLIENT_ID="test-client-id",
        GITHUB_OAUTH_CLIENT_SECRET="test-client-secret",
        GITHUB_OAUTH_REDIRECT_URL="http://localhost:8000/auth/callback",
        OAUTH_SCOPES="repo,read:org",
        SESSION_MAX_AGE_SECONDS=60,
        COOKIE_SECURE=False,
    )


def _make_request_with_cookies(**cookies: str) -> Request:
    """Hand-roll a Starlette ``Request`` scope for cookie-level unit tests.

    Avoids spinning up a TestClient for tests that only exercise the
    ``read_session`` / ``verify_oauth_state`` plumbing.
    """
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", cookie_header.encode())] if cookies else [],
        "query_string": b"",
    }
    return Request(scope)


# ---------------------------------------------------------------------------
# Cookie roundtrip / tampering / expiry
# ---------------------------------------------------------------------------


class SessionCookieRoundtripTests(unittest.TestCase):
    def test_signed_cookie_decodes_back_to_same_session(self) -> None:
        with _patched_settings():
            session = auth.Session(token="gho_real_token", login="maksimf")
            # ``write_session`` mutates a real Response; the TestClient
            # path covers that. Here we use the serializer directly to
            # avoid the framework round-trip.
            signed = auth._session_serializer().dumps(
                {"token": session.token, "login": session.login}
            )
            req = _make_request_with_cookies(gh_session=signed)
            recovered = auth.read_session(req)

        assert recovered is not None
        self.assertEqual(recovered.token, "gho_real_token")
        self.assertEqual(recovered.login, "maksimf")

    def test_login_is_lower_cased_on_read(self) -> None:
        with _patched_settings():
            signed = auth._session_serializer().dumps(
                {"token": "tok", "login": "MaksimF"}
            )
            req = _make_request_with_cookies(gh_session=signed)
            recovered = auth.read_session(req)

        assert recovered is not None
        self.assertEqual(recovered.login, "maksimf")

    def test_missing_cookie_returns_none(self) -> None:
        with _patched_settings():
            req = _make_request_with_cookies()
            self.assertIsNone(auth.read_session(req))

    def test_tampered_signature_returns_none(self) -> None:
        with _patched_settings():
            signed = auth._session_serializer().dumps(
                {"token": "tok", "login": "maksimf"}
            )
            tampered = signed[:-2] + "xx"
            req = _make_request_with_cookies(gh_session=tampered)
            self.assertIsNone(auth.read_session(req))

    def test_wrong_signing_key_returns_none(self) -> None:
        """Rotating SESSION_SECRET should log everyone out."""
        with _patched_settings():
            signed = auth._session_serializer().dumps(
                {"token": "tok", "login": "maksimf"}
            )
        with mock.patch.object(settings, "SESSION_SECRET", "different-secret"):
            req = _make_request_with_cookies(gh_session=signed)
            self.assertIsNone(auth.read_session(req))

    def test_expired_cookie_returns_none(self) -> None:
        """``SESSION_MAX_AGE_SECONDS`` actually enforces expiry."""
        with _patched_settings():
            signed = auth._session_serializer().dumps(
                {"token": "tok", "login": "maksimf"}
            )

        # Backdate ``time.time`` past the configured max age so the
        # signed timestamp inside the cookie looks ancient. We need
        # ``itsdangerous``'s timestamp reader to see the slow clock.
        max_age = 60
        with mock.patch.object(settings, "SESSION_SECRET", _TEST_SECRET), \
             mock.patch.object(settings, "SESSION_MAX_AGE_SECONDS", max_age), \
             mock.patch("itsdangerous.timed.time.time",
                        return_value=time.time() + max_age + 10):
            req = _make_request_with_cookies(gh_session=signed)
            self.assertIsNone(auth.read_session(req))

    def test_malformed_payload_returns_none(self) -> None:
        with _patched_settings():
            # Sign a *string* (not the expected dict) so the payload
            # decodes but the type guard rejects it.
            bogus = auth._session_serializer().dumps("not-a-dict")
            req = _make_request_with_cookies(gh_session=bogus)
            self.assertIsNone(auth.read_session(req))

    def test_empty_token_or_login_returns_none(self) -> None:
        with _patched_settings():
            for payload in (
                {"token": "", "login": "maksimf"},
                {"token": "tok", "login": ""},
            ):
                signed = auth._session_serializer().dumps(payload)
                req = _make_request_with_cookies(gh_session=signed)
                self.assertIsNone(auth.read_session(req))


# ---------------------------------------------------------------------------
# OAuth state CSRF
# ---------------------------------------------------------------------------


class OAuthStateTests(unittest.TestCase):
    def test_verify_returns_true_for_matching_signed_state(self) -> None:
        with _patched_settings():
            # ``issue_oauth_state`` writes to a Response; mimic the
            # round-trip by signing a fresh value ourselves.
            original = "fresh-random-state"
            signed = auth._oauth_state_serializer().dumps(original)
            req = _make_request_with_cookies(gh_oauth_state=signed)
            self.assertTrue(auth.verify_oauth_state(req, original))

    def test_verify_returns_false_when_state_differs(self) -> None:
        with _patched_settings():
            signed = auth._oauth_state_serializer().dumps("real")
            req = _make_request_with_cookies(gh_oauth_state=signed)
            self.assertFalse(auth.verify_oauth_state(req, "spoofed"))

    def test_verify_returns_false_when_cookie_missing(self) -> None:
        with _patched_settings():
            req = _make_request_with_cookies()
            self.assertFalse(auth.verify_oauth_state(req, "anything"))

    def test_verify_returns_false_when_echoed_blank(self) -> None:
        with _patched_settings():
            signed = auth._oauth_state_serializer().dumps("real")
            req = _make_request_with_cookies(gh_oauth_state=signed)
            self.assertFalse(auth.verify_oauth_state(req, ""))

    def test_oauth_state_serializer_uses_different_salt(self) -> None:
        """A session-cookie value must not validate as an oauth-state cookie."""
        with _patched_settings():
            session_signed = auth._session_serializer().dumps("smuggled-state")
            req = _make_request_with_cookies(gh_oauth_state=session_signed)
            self.assertFalse(auth.verify_oauth_state(req, "smuggled-state"))


# ---------------------------------------------------------------------------
# Route gating (integration via FastAPI TestClient)
# ---------------------------------------------------------------------------


class RouteGatingTests(unittest.TestCase):
    """Exercise the real ``app.main`` app to confirm the dependency wiring."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._patch = _patched_settings()
        cls._patch.start()
        from app import main as main_module  # imported lazily inside the patch
        cls._main_module = main_module
        cls._client = TestClient(main_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client.close()
        cls._patch.stop()

    def _signed_cookie(self, login: str = "maksimf", token: str = "tok") -> str:
        return auth._session_serializer().dumps({"token": token, "login": login})

    def _with_session(self, login: str = "maksimf", token: str = "tok") -> TestClient:
        """Plant a signed session cookie on the shared TestClient for one test.

        Returns ``self._client``; callers should clear the jar afterwards
        with ``self._client.cookies.clear()`` so the cookie doesn't leak
        into siblings.
        """
        self._client.cookies.set("gh_session", self._signed_cookie(login, token))
        return self._client

    # --- HTML routes redirect when signed out --------------------------------

    def test_root_redirects_to_login_when_signed_out(self) -> None:
        r = self._client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("location"), "/login")

    def test_login_page_serves_html_when_signed_out(self) -> None:
        r = self._client.get("/login", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn("SIGN IN", r.text.upper())

    def test_login_page_redirects_when_already_signed_in(self) -> None:
        try:
            client = self._with_session()
            r = client.get("/login", follow_redirects=False)
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("location"), "/")

    def test_root_serves_dashboard_when_signed_in(self) -> None:
        try:
            client = self._with_session()
            r = client.get("/", follow_redirects=False)
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 200)
        # The dashboard now hosts the React SPA mount point.
        self.assertIn('id="root"', r.text)

    # --- API routes return 401 when signed out -------------------------------

    def test_me_returns_401_when_signed_out(self) -> None:
        r = self._client.get("/me")
        self.assertEqual(r.status_code, 401)

    def test_dashboard_returns_401_when_signed_out(self) -> None:
        r = self._client.get("/api/dashboard")
        self.assertEqual(r.status_code, 401)

    def test_refresh_returns_401_when_signed_out(self) -> None:
        r = self._client.post("/refresh")
        self.assertEqual(r.status_code, 401)

    def test_merge_returns_401_when_signed_out(self) -> None:
        r = self._client.post("/pulls/acme/widgets/1/merge")
        self.assertEqual(r.status_code, 401)

    # --- /me round-trip ------------------------------------------------------

    def test_me_returns_login_when_signed_in(self) -> None:
        try:
            client = self._with_session(login="maksimf")
            r = client.get("/me")
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["login"], "maksimf")
        self.assertIn("avatar_url", body)
        self.assertIn("maksimf", body["avatar_url"])

    # --- OAuth start + logout ------------------------------------------------

    def test_auth_start_redirects_to_github_and_sets_state_cookie(self) -> None:
        r = self._client.get("/auth/start", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        loc = r.headers.get("location", "")
        self.assertTrue(loc.startswith("https://github.com/login/oauth/authorize"))
        self.assertIn("client_id=test-client-id", loc)
        self.assertIn("scope=repo%2Cread%3Aorg", loc)
        # State cookie should land on the response.
        self.assertIn("gh_oauth_state", r.cookies)

    def test_callback_rejects_mismatched_state(self) -> None:
        # No state cookie at all -> rejected without ever calling GitHub.
        r = self._client.get(
            "/auth/callback",
            params={"code": "abc", "state": "spoofed"},
            follow_redirects=False,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("state mismatch", r.text.lower())

    def test_callback_rejects_missing_code(self) -> None:
        r = self._client.get(
            "/auth/callback",
            params={"state": "anything"},
            follow_redirects=False,
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("missing oauth code", r.text.lower())

    def test_callback_happy_path_sets_session_cookie(self) -> None:
        # Pre-sign the CSRF cookie + plant it on the client jar so the
        # callback's ``verify_oauth_state`` succeeds without us needing
        # to hit /auth/start first.
        csrf = "test-csrf-value"
        signed_csrf = auth._oauth_state_serializer().dumps(csrf)
        self._client.cookies.set("gh_oauth_state", signed_csrf)

        async def _fake_exchange(*args: Any, **kwargs: Any) -> str:
            return "gho_real_token"

        async def _fake_login(*args: Any, **kwargs: Any) -> str:
            return "MaksimF"

        try:
            with mock.patch.object(auth, "exchange_code", _fake_exchange), \
                 mock.patch.object(auth, "fetch_viewer_login", _fake_login):
                r = self._client.get(
                    "/auth/callback",
                    params={"code": "abc", "state": csrf},
                    follow_redirects=False,
                )
        finally:
            self._client.cookies.clear()

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("location"), "/")
        self.assertIn("gh_session", r.cookies)

        # Decoded payload should round-trip with login lower-cased.
        signed = r.cookies["gh_session"]
        payload = auth._session_serializer().loads(signed, max_age=60)
        self.assertEqual(payload, {"token": "gho_real_token", "login": "MaksimF"})

    def test_logout_clears_session_cookie(self) -> None:
        try:
            client = self._with_session()
            r = client.post("/logout", follow_redirects=False)
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers.get("location"), "/")
        # ``delete_cookie`` lands a Set-Cookie with Max-Age=0; httpx
        # surfaces that as an absent cookie value on the response jar.
        set_cookie = r.headers.get("set-cookie", "")
        self.assertIn("gh_session=", set_cookie)
        self.assertIn("Max-Age=0", set_cookie)


# ---------------------------------------------------------------------------
# Smoke test for the FastAPI app builds cleanly even without OAuth creds
# (so a ``--help`` or import-time error doesn't crash).
# ---------------------------------------------------------------------------


class AppImportSmokeTests(unittest.TestCase):
    def test_app_module_imports_with_default_settings(self) -> None:
        # Just confirms no import-time side-effects require OAuth secrets;
        # the auth helpers only blow up at sign-in time.
        from app import main  # noqa: F401
        self.assertIsInstance(main.app, FastAPI)


if __name__ == "__main__":
    unittest.main()
