"""Tests for the per-viewer reviewer-tracking model logic.

The reviewer is now owned entirely by the client (localStorage -> query
param) and resolved per request in :mod:`app.serialize`, so there's no
``POST /settings/reviewer`` endpoint or ``state.set_reviewer`` cache to
test anymore. What remains is the model-level rule that the column /
chip placement is built on: :meth:`PR.is_approved_by`,
:meth:`PR.is_review_requested_from`, :meth:`PR.column_for`, and the
matching ``StackNode`` method.
"""
from __future__ import annotations

import unittest

from app.model import PR, Checks, StackNode


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

    def test_is_ready_without_preview_url(self) -> None:
        pr = _pr()
        pr_no_preview = pr.model_copy(update={"preview_url": None})
        self.assertTrue(pr_no_preview.is_ready)
        self.assertEqual(pr_no_preview.column_for(None), "ready")


class MultiReviewerColumnTests(unittest.TestCase):
    def test_column_promotes_when_any_tracked_reviewer_approves(self) -> None:
        pr = _pr(approvers=("bob",))
        # bob is one of several tracked reviewers -> approved.
        self.assertEqual(pr.column_for(["alice", "bob", "carol"]), "approved")

    def test_column_stays_ready_when_no_tracked_reviewer_approved(self) -> None:
        pr = _pr(approvers=("dave",))
        self.assertEqual(pr.column_for(["alice", "bob"]), "ready")

    def test_empty_reviewer_list_never_approves(self) -> None:
        pr = _pr(approvers=("alice",))
        self.assertEqual(pr.column_for([]), "ready")

    def test_list_matching_is_case_insensitive(self) -> None:
        pr = _pr(approvers=("Alice",))
        self.assertEqual(pr.column_for(["ALICE", "bob"]), "approved")


class NormalizeReviewersTests(unittest.TestCase):
    def test_handles_str_iterable_and_none(self) -> None:
        from app.model import normalize_reviewers

        self.assertEqual(normalize_reviewers(None), set())
        self.assertEqual(normalize_reviewers(""), set())
        self.assertEqual(normalize_reviewers("  Alice "), {"alice"})
        self.assertEqual(
            normalize_reviewers(["Alice", " bob", "", "ALICE"]),
            {"alice", "bob"},
        )


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


if __name__ == "__main__":
    unittest.main()
