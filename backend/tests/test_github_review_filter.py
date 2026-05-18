import unittest

from app.github import GitHubClient


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
        # ``latestReviews`` only shows the most recent review per reviewer,
        # so switching back to CHANGES_REQUESTED naturally unhides the PR.
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
