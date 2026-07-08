"""Integration tests for the ``GET /attachments`` token proxy.

The proxy exists so the SPA can render images/videos uploaded into PR
bodies (``github.com/user-attachments/assets/...``). Those need the
viewer's token, and GitHub answers with a 302 to a short-lived signed S3
URL. We assert the happy-path redirect, the SSRF allowlist, and auth
gating.
"""
from __future__ import annotations

import unittest
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from app import auth
from app.config import settings

_TEST_SECRET = "test-session-secret-do-not-use-in-prod"
_ASSET_URL = "https://github.com/user-attachments/assets/abc-123"
_SIGNED_URL = "https://github-production-user-asset-6210df.s3.amazonaws.com/x.mp4?sig=1"


def _patched_settings():
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


class AttachmentProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._patch = _patched_settings()
        cls._patch.start()
        from app import main as main_module

        cls._main_module = main_module
        cls._client = TestClient(main_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client.close()
        cls._patch.stop()

    def _install_transport(self, handler) -> None:
        self._main_module.app.state.http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        )

    def _signed_cookie(self, token: str = "tok") -> str:
        return auth._session_serializer().dumps({"token": token, "login": "maksimf"})

    def _sign_in(self, token: str = "tok") -> None:
        self._client.cookies.set("gh_session", self._signed_cookie(token))

    def test_redirects_to_signed_asset_with_token(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(302, headers={"location": _SIGNED_URL})

        self._install_transport(handler)
        try:
            self._sign_in("ghp_secret")
            r = self._client.get(
                "/attachments", params={"url": _ASSET_URL}, follow_redirects=False
            )
        finally:
            self._client.cookies.clear()

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("location"), _SIGNED_URL)
        # The viewer's token authenticated the upstream fetch.
        self.assertEqual(len(seen), 1)
        self.assertEqual(str(seen[0].url), _ASSET_URL)
        self.assertEqual(seen[0].headers.get("Authorization"), "bearer ghp_secret")

    def test_rejects_non_attachment_host(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("must not hit upstream for a rejected URL")

        self._install_transport(handler)
        try:
            self._sign_in()
            r = self._client.get(
                "/attachments",
                params={"url": "https://evil.example.com/steal"},
                follow_redirects=False,
            )
        finally:
            self._client.cookies.clear()

        self.assertEqual(r.status_code, 400)

    def test_rejects_github_non_attachment_path(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("must not hit upstream for a rejected URL")

        self._install_transport(handler)
        try:
            self._sign_in()
            r = self._client.get(
                "/attachments",
                params={"url": "https://github.com/maksimf/repo/settings"},
                follow_redirects=False,
            )
        finally:
            self._client.cookies.clear()

        self.assertEqual(r.status_code, 400)

    def test_requires_session(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("must not hit upstream when signed out")

        self._install_transport(handler)
        r = self._client.get(
            "/attachments", params={"url": _ASSET_URL}, follow_redirects=False
        )
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
