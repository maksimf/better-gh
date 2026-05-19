import unittest
from unittest.mock import patch

from app.github import GitHubClient, _compile_linear_pattern


def _node(*, title: str = "", body: str = "") -> dict:
    return {"title": title, "body": body}


class LinearTicketPatternTests(unittest.TestCase):
    def test_returns_none_when_prefix_empty(self) -> None:
        self.assertIsNone(_compile_linear_pattern(""))

    def test_matches_three_digits(self) -> None:
        pattern = _compile_linear_pattern("ENG-")
        assert pattern is not None
        match = pattern.search("Fix ENG-123 followup")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group(1), "123")

    def test_matches_more_than_three_digits(self) -> None:
        pattern = _compile_linear_pattern("ENG-")
        assert pattern is not None
        match = pattern.search("ENG-12345: refactor poller")
        assert match is not None
        self.assertEqual(match.group(1), "12345")

    def test_rejects_two_digits(self) -> None:
        pattern = _compile_linear_pattern("ENG-")
        assert pattern is not None
        self.assertIsNone(pattern.search("ENG-12 too short"))

    def test_rejects_concatenated_prefix(self) -> None:
        pattern = _compile_linear_pattern("ENG-")
        assert pattern is not None
        # "FOOENG-1234" shouldn't match -- the prefix has to be word-anchored.
        self.assertIsNone(pattern.search("FOOENG-1234"))

    def test_rejects_trailing_letters(self) -> None:
        pattern = _compile_linear_pattern("ENG-")
        assert pattern is not None
        # Trailing alpha breaks the word boundary on the digit side.
        self.assertIsNone(pattern.search("ENG-1234abc"))


class FindLinearUrlTests(unittest.TestCase):
    """End-to-end: ``GitHubClient._find_linear_url`` against patched settings."""

    def _patch_settings(self, **overrides: object):
        defaults = {
            "LINEAR_TICKET_PREFIX": "ENG-",
            "LINEAR_WORKSPACE_URL": "https://linear.app/clearest",
        }
        defaults.update(overrides)
        return patch.multiple("app.github.settings", **defaults)

    def test_finds_ticket_in_title(self) -> None:
        with self._patch_settings():
            url = GitHubClient._find_linear_url(
                _node(title="ENG-1234 fix flaky test", body="")
            )
        self.assertEqual(url, "https://linear.app/clearest/issue/ENG-1234")

    def test_finds_ticket_in_body_when_title_has_none(self) -> None:
        with self._patch_settings():
            url = GitHubClient._find_linear_url(
                _node(title="refactor", body="Closes ENG-9876.")
            )
        self.assertEqual(url, "https://linear.app/clearest/issue/ENG-9876")

    def test_title_wins_over_body(self) -> None:
        with self._patch_settings():
            url = GitHubClient._find_linear_url(
                _node(title="ENG-111", body="Closes ENG-222")
            )
        self.assertEqual(url, "https://linear.app/clearest/issue/ENG-111")

    def test_returns_none_when_no_match(self) -> None:
        with self._patch_settings():
            url = GitHubClient._find_linear_url(
                _node(title="no ticket here", body="nothing either")
            )
        self.assertIsNone(url)

    def test_disabled_when_prefix_empty(self) -> None:
        with self._patch_settings(LINEAR_TICKET_PREFIX=""):
            url = GitHubClient._find_linear_url(_node(title="ENG-1234", body=""))
        self.assertIsNone(url)

    def test_disabled_when_workspace_url_empty(self) -> None:
        with self._patch_settings(LINEAR_WORKSPACE_URL=""):
            url = GitHubClient._find_linear_url(_node(title="ENG-1234", body=""))
        self.assertIsNone(url)

    def test_strips_trailing_slash_from_workspace(self) -> None:
        with self._patch_settings(
            LINEAR_WORKSPACE_URL="https://linear.app/clearest/"
        ):
            url = GitHubClient._find_linear_url(
                _node(title="ENG-1234", body="")
            )
        self.assertEqual(url, "https://linear.app/clearest/issue/ENG-1234")

    def test_handles_custom_prefix(self) -> None:
        with self._patch_settings(LINEAR_TICKET_PREFIX="PROD-"):
            url = GitHubClient._find_linear_url(
                _node(title="PROD-5550 hotfix", body="")
            )
        self.assertEqual(url, "https://linear.app/clearest/issue/PROD-5550")


if __name__ == "__main__":
    unittest.main()
