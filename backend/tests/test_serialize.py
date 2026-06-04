"""Tests for the JSON serialization that feeds the React SPA.

Covers the per-viewer derived fields (column / approved /
review_requested), the stack layout fields, repo counts, the effective
reviewer fallback, and the error shape.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from app import serialize
from app.config import settings
from app.model import PR, Checks, ReviewPR


def _pr(
    *,
    number: int,
    repo: str = "acme/widgets",
    is_draft: bool = False,
    approvers: tuple[str, ...] = (),
    requested: tuple[str, ...] = (),
    base_ref: str = "",
    head_ref: str = "",
    preview: str | None = "https://preview.example/x",
) -> PR:
    return PR(
        number=number,
        title=f"PR {number}",
        url=f"https://github.com/{repo}/pull/{number}",
        repo=repo,
        author="someone",
        is_draft=is_draft,
        checks=Checks(passed=1),
        comments_human=0,
        comments_bot=0,
        preview_url=preview,
        conflicts=0,
        updated_at="2026-05-20T10:00:00Z",
        requested_reviewers=requested,
        approver_logins=approvers,
        base_ref=base_ref,
        head_ref=head_ref,
    )


def _review(*, number: int, repo: str = "acme/widgets") -> ReviewPR:
    return ReviewPR(
        number=number,
        title=f"Review {number}",
        url=f"https://github.com/{repo}/pull/{number}",
        repo=repo,
        author="other",
        is_draft=False,
        checks=Checks(passed=1),
        conflicts=0,
        updated_at="2026-05-20T10:00:00Z",
        requested_at="2026-05-20T09:00:00Z",
    )


class EffectiveReviewerTests(unittest.TestCase):
    def test_none_falls_back_to_env_default(self) -> None:
        with mock.patch.object(settings, "REVIEWER_LOGIN", "Default-Rev"):
            self.assertEqual(serialize.effective_reviewer(None), "default-rev")

    def test_empty_string_means_no_reviewer(self) -> None:
        self.assertEqual(serialize.effective_reviewer(""), "")

    def test_explicit_value_is_trimmed_and_lowered(self) -> None:
        self.assertEqual(serialize.effective_reviewer("  Alice\n"), "alice")


class SerializePrTests(unittest.TestCase):
    def test_derives_column_and_reviewer_flags(self) -> None:
        pr = _pr(number=1, approvers=("alice",), requested=("alice",))
        out = serialize.serialize_pr(pr, "alice")
        self.assertEqual(out["column"], "approved")
        self.assertTrue(out["approved"])
        self.assertTrue(out["review_requested"])
        self.assertEqual(out["checks"]["passed"], 1)
        self.assertEqual(out["stack_id"], None)
        self.assertEqual(out["stack_nodes"], [])

    def test_non_matching_reviewer_keeps_pr_out_of_approved(self) -> None:
        pr = _pr(number=1, approvers=("alice",))
        out = serialize.serialize_pr(pr, "bob")
        self.assertEqual(out["column"], "ready")
        self.assertFalse(out["approved"])


class SerializeDashboardTests(unittest.TestCase):
    def test_repo_counts_and_payload_shape(self) -> None:
        prs = [_pr(number=1, repo="acme/a"), _pr(number=2, repo="acme/a")]
        reviews = [_review(number=3, repo="acme/b")]
        payload = serialize.serialize_dashboard(
            prs=prs,
            reviews=reviews,
            reviewer_login="alice",
            last_polled_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
            error_message="",
            error_reset_at=None,
            poll_interval_seconds=300,
        )
        self.assertEqual(payload["reviewer"], "alice")
        self.assertEqual(payload["poll_interval_seconds"], 300)
        self.assertEqual(payload["last_polled_at"], "2026-05-20T10:00:00Z")
        self.assertIsNone(payload["error"])
        self.assertEqual(len(payload["prs"]), 2)
        self.assertEqual(len(payload["reviews"]), 1)
        repos = {r["repo"]: r["count"] for r in payload["repos"]}
        self.assertEqual(repos, {"acme/a": 2, "acme/b": 1})

    def test_error_is_serialized_with_iso_reset(self) -> None:
        payload = serialize.serialize_dashboard(
            prs=[],
            reviews=[],
            reviewer_login="",
            last_polled_at=None,
            error_message="rate limited",
            error_reset_at=datetime(2026, 5, 20, 11, 0, tzinfo=timezone.utc),
            poll_interval_seconds=300,
        )
        self.assertEqual(payload["error"]["message"], "rate limited")
        self.assertEqual(payload["error"]["reset_at"], "2026-05-20T11:00:00Z")
        self.assertEqual(payload["reviewer"], "")

    def test_stack_split_across_columns_serializes_nodes(self) -> None:
        # B (feature-b) stacks on A (feature-a). A is a draft (-> progress);
        # B is approved by the tracked reviewer (-> approved). Split columns
        # => stack_co_column False and the inline tree nodes are present.
        a = _pr(number=1, is_draft=True, head_ref="feature-a", base_ref="main")
        b = _pr(
            number=2,
            approvers=("alice",),
            head_ref="feature-b",
            base_ref="feature-a",
        )
        payload = serialize.serialize_dashboard(
            prs=[a, b],
            reviews=[],
            reviewer_login="alice",
            last_polled_at=None,
            error_message="",
            error_reset_at=None,
            poll_interval_seconds=300,
        )
        by_number = {pr["number"]: pr for pr in payload["prs"]}
        self.assertEqual(by_number[1]["column"], "progress")
        self.assertEqual(by_number[2]["column"], "approved")
        self.assertFalse(by_number[1]["stack_co_column"])
        self.assertEqual(by_number[1]["stack_id"], "acme/widgets#1")
        # Inline tree carries both nodes with their per-viewer columns.
        node_cols = {n["number"]: n["column"] for n in by_number[1]["stack_nodes"]}
        self.assertEqual(node_cols, {1: "progress", 2: "approved"})


if __name__ == "__main__":
    unittest.main()
