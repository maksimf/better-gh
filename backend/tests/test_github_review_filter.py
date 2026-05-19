import unittest

from app.github import GitHubClient


def _node(
    *,
    requested_at: str = "",
    review_at: str = "",
    review_state: str = "CHANGES_REQUESTED",
) -> dict:
    timeline_nodes = []
    if requested_at:
        timeline_nodes.append(
            {
                "createdAt": requested_at,
                "requestedReviewer": {"__typename": "User", "login": "maksimf"},
            }
        )

    review_nodes = []
    if review_at:
        review_nodes.append(
            {
                "state": review_state,
                "submittedAt": review_at,
                "author": {"login": "maksimf"},
            }
        )

    return {
        "timelineItems": {"nodes": timeline_nodes},
        "reviews": {"nodes": review_nodes},
    }


class ReviewFilterTests(unittest.TestCase):
    def test_hides_when_changes_requested_is_newer_than_request(self) -> None:
        node = _node(
            requested_at="2026-05-06T07:00:00Z",
            review_at="2026-05-06T07:26:05Z",
            review_state="CHANGES_REQUESTED",
        )

        self.assertTrue(GitHubClient._viewer_review_resolved(node, "maksimf"))

    def test_shows_when_changes_requested_then_review_requested_again(self) -> None:
        node = _node(
            requested_at="2026-05-08T18:06:01Z",
            review_at="2026-05-06T07:26:05Z",
            review_state="CHANGES_REQUESTED",
        )

        self.assertFalse(GitHubClient._viewer_review_resolved(node, "maksimf"))

    def test_shows_when_request_timestamp_is_missing_for_changes_requested(self) -> None:
        node = _node(
            review_at="2026-05-06T07:26:05Z",
            review_state="CHANGES_REQUESTED",
        )

        self.assertFalse(GitHubClient._viewer_review_resolved(node, "maksimf"))

    def test_hides_when_viewer_has_approved_regardless_of_re_request(self) -> None:
        # Author re-requested review after the viewer approved -- with the
        # "already approved means done" rule, the PR should still be hidden.
        node = _node(
            requested_at="2026-05-08T18:06:01Z",
            review_at="2026-05-06T07:26:05Z",
            review_state="APPROVED",
        )

        self.assertTrue(GitHubClient._viewer_review_resolved(node, "maksimf"))

    def test_hides_when_viewer_approved_and_request_timestamp_is_missing(self) -> None:
        node = _node(
            review_at="2026-05-06T07:26:05Z",
            review_state="APPROVED",
        )

        self.assertTrue(GitHubClient._viewer_review_resolved(node, "maksimf"))

    def test_uses_latest_review_state_when_viewer_has_both(self) -> None:
        # Viewer approved, then later asked for changes -- their latest
        # substantive state is CHANGES_REQUESTED, so the "approved means
        # done" shortcut should NOT fire; instead we fall through to the
        # request-vs-review comparison.
        node = {
            "timelineItems": {
                "nodes": [
                    {
                        "createdAt": "2026-05-10T09:00:00Z",
                        "requestedReviewer": {
                            "__typename": "User",
                            "login": "maksimf",
                        },
                    }
                ]
            },
            "reviews": {
                "nodes": [
                    {
                        "state": "APPROVED",
                        "submittedAt": "2026-05-06T07:26:05Z",
                        "author": {"login": "maksimf"},
                    },
                    {
                        "state": "CHANGES_REQUESTED",
                        "submittedAt": "2026-05-09T12:00:00Z",
                        "author": {"login": "maksimf"},
                    },
                ]
            },
        }

        # Latest substantive review (CHANGES_REQUESTED at 05-09) is older
        # than the latest request (05-10), so the PR is still pending.
        self.assertFalse(GitHubClient._viewer_review_resolved(node, "maksimf"))


class ViewerAlreadyApprovedTests(unittest.TestCase):
    def test_true_when_viewer_latest_review_is_approved(self) -> None:
        node = {
            "latestReviews": {
                "nodes": [
                    {"state": "APPROVED", "author": {"login": "maksimf"}},
                ]
            }
        }

        self.assertTrue(GitHubClient._viewer_already_approved(node, "maksimf"))

    def test_false_when_viewer_latest_review_is_changes_requested(self) -> None:
        node = {
            "latestReviews": {
                "nodes": [
                    {"state": "CHANGES_REQUESTED", "author": {"login": "maksimf"}},
                ]
            }
        }

        self.assertFalse(GitHubClient._viewer_already_approved(node, "maksimf"))

    def test_false_when_viewer_has_no_review(self) -> None:
        node = {
            "latestReviews": {
                "nodes": [
                    {"state": "APPROVED", "author": {"login": "someoneelse"}},
                ]
            }
        }

        self.assertFalse(GitHubClient._viewer_already_approved(node, "maksimf"))

    def test_false_when_viewer_login_is_empty(self) -> None:
        node = {
            "latestReviews": {
                "nodes": [
                    {"state": "APPROVED", "author": {"login": "maksimf"}},
                ]
            }
        }

        self.assertFalse(GitHubClient._viewer_already_approved(node, ""))

    def test_match_is_case_insensitive(self) -> None:
        node = {
            "latestReviews": {
                "nodes": [
                    {"state": "APPROVED", "author": {"login": "MaksimF"}},
                ]
            }
        }

        self.assertTrue(GitHubClient._viewer_already_approved(node, "maksimf"))


if __name__ == "__main__":
    unittest.main()
