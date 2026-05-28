"""Tests for the per-viewer reviewer-tracking setting.

Covers the three layers:

* Model-level: :meth:`PR.is_approved_by`,
  :meth:`PR.is_review_requested_from`, :meth:`PR.column_for` and the
  matching ``StackNode`` method.
* State-level: :func:`state.set_reviewer` / :func:`state.get_reviewer`
  bookkeeping.
* Route-level: ``POST /settings/reviewer`` (auth gate, validation,
  precedence) + the cookie/env fallback in the render path.
"""
from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, state
from app.config import settings
from app.model import PR, Checks, StackNode


_TEST_SECRET = "test-session-secret-do-not-use-in-prod"


def _patched_settings():
    """Match ``test_auth.py``'s patching pattern so the modules share a
    secret + OAuth config for the duration of one test class."""
    return mock.patch.multiple(
        settings,
        SESSION_SECRET=_TEST_SECRET,
        GITHUB_OAUTH_CLIENT_ID="test-client-id",
        GITHUB_OAUTH_CLIENT_SECRET="test-client-secret",
        GITHUB_OAUTH_REDIRECT_URL="http://localhost:8000/auth/callback",
        OAUTH_SCOPES="repo,read:org",
        SESSION_MAX_AGE_SECONDS=60,
        COOKIE_SECURE=False,
        REVIEWER_LOGIN="env-default",
    )


def _pr(*, approvers=(), requested=()) -> PR:
    return PR(
        number=1,
        title="A PR",
        url="https://github.com/acme/widgets/pull/1",
        repo="acme/widgets",
        author="someone",
        is_draft=False,
        checks=Checks(passed=1),
        comments_human=0,
        comments_bot=0,
        preview_url="https://preview.example/x",
        conflicts=0,
        updated_at="2026-05-20T10:00:00Z",
        requested_reviewers=tuple(requested),
        approver_logins=tuple(approvers),
    )


# ---------------------------------------------------------------------------
# Model-level
# ---------------------------------------------------------------------------


class PRReviewerMethodsTests(unittest.TestCase):
    def test_is_approved_by_matches_case_insensitive(self) -> None:
        pr = _pr(approvers=("Alice", "Bob"))
        self.assertTrue(pr.is_approved_by("alice"))
        self.assertTrue(pr.is_approved_by("ALICE"))
        self.assertTrue(pr.is_approved_by("BOB"))
        self.assertFalse(pr.is_approved_by("charlie"))

    def test_is_approved_by_treats_blank_reviewer_as_not_approved(self) -> None:
        pr = _pr(approvers=("alice",))
        self.assertFalse(pr.is_approved_by(""))
        self.assertFalse(pr.is_approved_by(None))
        self.assertFalse(pr.is_approved_by("   "))

    def test_is_review_requested_from_matches_case_insensitive(self) -> None:
        pr = _pr(requested=("Charlie",))
        self.assertTrue(pr.is_review_requested_from("charlie"))
        self.assertFalse(pr.is_review_requested_from("alice"))

    def test_column_for_promotes_to_approved_only_for_matching_reviewer(self) -> None:
        pr = _pr(approvers=("alice",))
        # Ready otherwise -> would be 'ready' without the reviewer match.
        self.assertEqual(pr.column_for("alice"), "approved")
        self.assertEqual(pr.column_for("bob"), "ready")
        self.assertEqual(pr.column_for(""), "ready")
        self.assertEqual(pr.column_for(None), "ready")


class StackNodeReviewerMethodTests(unittest.TestCase):
    def test_stack_node_column_for_mirrors_pr(self) -> None:
        node = StackNode(
            number=1,
            title="t",
            url="u",
            repo="r/r",
            depth=0,
            parent_number=None,
            is_ready=True,
            approver_logins=("alice",),
        )
        self.assertEqual(node.column_for("alice"), "approved")
        self.assertEqual(node.column_for("bob"), "ready")


# ---------------------------------------------------------------------------
# State-level
# ---------------------------------------------------------------------------


class SetReviewerStateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        # Each test creates state for a unique login; clear it so
        # other test classes start from a clean dict.
        await state.shutdown()

    async def test_set_reviewer_returns_changed_when_value_differs(self) -> None:
        changed, value = await state.set_reviewer("alice-test-1", "bob")
        self.assertTrue(changed)
        self.assertEqual(value, "bob")
        self.assertEqual(state.get_reviewer("alice-test-1"), "bob")

    async def test_set_reviewer_returns_unchanged_on_no_op(self) -> None:
        await state.set_reviewer("alice-test-2", "bob")
        changed, _ = await state.set_reviewer("alice-test-2", "bob")
        self.assertFalse(changed)

    async def test_set_reviewer_distinguishes_none_from_empty(self) -> None:
        # None means "fall back to env default", "" means "explicitly
        # no reviewer". Bookkeeping must differentiate.
        await state.set_reviewer("alice-test-3", None)
        self.assertIsNone(state.get_reviewer("alice-test-3"))
        changed, value = await state.set_reviewer("alice-test-3", "")
        self.assertTrue(changed)
        self.assertEqual(value, "")
        self.assertEqual(state.get_reviewer("alice-test-3"), "")

    async def test_set_reviewer_strips_whitespace(self) -> None:
        _, value = await state.set_reviewer("alice-test-4", "  bob\n")
        self.assertEqual(value, "bob")


# ---------------------------------------------------------------------------
# Route-level
# ---------------------------------------------------------------------------


class ReviewerEndpointTests(unittest.TestCase):
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

    def _signed_cookie(self, login: str = "maksimf", token: str = "tok") -> str:
        return auth._session_serializer().dumps({"token": token, "login": login})

    def test_post_settings_reviewer_requires_auth(self) -> None:
        # No session cookie planted -> 401, not a redirect.
        r = self._client.post("/settings/reviewer", json={"reviewer": "alice"})
        self.assertEqual(r.status_code, 401)

    def test_post_settings_reviewer_accepts_login(self) -> None:
        try:
            self._client.cookies.set("gh_session", self._signed_cookie())
            r = self._client.post(
                "/settings/reviewer", json={"reviewer": "alice"}
            )
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 204)

    def test_post_settings_reviewer_accepts_null_to_clear(self) -> None:
        try:
            self._client.cookies.set("gh_session", self._signed_cookie())
            r = self._client.post(
                "/settings/reviewer", json={"reviewer": None}
            )
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 204)

    def test_post_settings_reviewer_rejects_over_long_login(self) -> None:
        try:
            self._client.cookies.set("gh_session", self._signed_cookie())
            r = self._client.post(
                "/settings/reviewer", json={"reviewer": "x" * 40}
            )
        finally:
            self._client.cookies.clear()
        # GitHub logins cap at 39 chars; pydantic ``max_length`` rejects 40+.
        self.assertEqual(r.status_code, 422)

    def test_post_settings_reviewer_rejects_unknown_keys_gracefully(self) -> None:
        # Empty body -> field is optional, defaults to None -> 204.
        try:
            self._client.cookies.set("gh_session", self._signed_cookie())
            r = self._client.post("/settings/reviewer", json={})
        finally:
            self._client.cookies.clear()
        self.assertEqual(r.status_code, 204)

    def test_resolve_reviewer_prefers_user_state_over_cookie(self) -> None:
        """``_resolve_reviewer`` should pick the cached state value
        first; the cookie is only a fallback for the cold-cache window
        before SSE has populated UserState."""
        import asyncio

        from starlette.requests import Request

        try:
            asyncio.run(state.set_reviewer("maksimf", "from-state"))
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/prs.html",
                "headers": [(b"cookie", b"reviewer_pref=from-cookie")],
                "query_string": b"",
            }
            req = Request(scope)
            self.assertEqual(
                self._main_module._resolve_reviewer(req, "maksimf"),
                "from-state",
            )
        finally:
            asyncio.run(state.shutdown())

    def test_resolve_reviewer_falls_back_to_cookie_when_state_empty(self) -> None:
        from starlette.requests import Request
        # No state set for "fresh-user"; cookie should win.
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/prs.html",
            "headers": [(b"cookie", b"reviewer_pref=from-cookie")],
            "query_string": b"",
        }
        req = Request(scope)
        self.assertEqual(
            self._main_module._resolve_reviewer(req, "fresh-user"),
            "from-cookie",
        )

    def test_resolve_reviewer_returns_none_when_neither_set(self) -> None:
        from starlette.requests import Request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/prs.html",
            "headers": [],
            "query_string": b"",
        }
        req = Request(scope)
        self.assertIsNone(
            self._main_module._resolve_reviewer(req, "never-seen-this-user")
        )


if __name__ == "__main__":
    unittest.main()
