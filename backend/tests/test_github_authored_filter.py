import unittest

from app.github import GitHubClient


def _node(*, author: str, assignees: list[str] | None = None) -> dict:
    assignee_nodes: list[dict] | None
    if assignees is None:
        assignee_nodes = None
    else:
        assignee_nodes = [{"login": login} for login in assignees]
    return {
        "author": {"login": author},
        "assignees": {"nodes": assignee_nodes} if assignee_nodes is not None else None,
    }


class DelegatedAuthoredFilterTests(unittest.TestCase):
    def test_hides_when_viewer_authored_and_only_other_is_assignee(self) -> None:
        node = _node(author="maksimf", assignees=["someoneelse"])

        self.assertTrue(GitHubClient._is_delegated_authored_pr(node, "maksimf"))

    def test_keeps_when_viewer_authored_and_no_assignees(self) -> None:
        node = _node(author="maksimf", assignees=[])

        self.assertFalse(GitHubClient._is_delegated_authored_pr(node, "maksimf"))

    def test_keeps_when_viewer_authored_and_is_one_of_the_assignees(self) -> None:
        node = _node(author="maksimf", assignees=["someoneelse", "maksimf"])

        self.assertFalse(GitHubClient._is_delegated_authored_pr(node, "maksimf"))

    def test_keeps_when_viewer_did_not_author(self) -> None:
        node = _node(author="someoneelse", assignees=["anotherperson"])

        self.assertFalse(GitHubClient._is_delegated_authored_pr(node, "maksimf"))

    def test_author_and_viewer_comparison_is_case_insensitive(self) -> None:
        node = _node(author="MaksimF", assignees=["SomeoneElse"])

        self.assertTrue(GitHubClient._is_delegated_authored_pr(node, "maksimf"))

    def test_returns_false_when_viewer_login_is_empty(self) -> None:
        node = _node(author="maksimf", assignees=["someoneelse"])

        self.assertFalse(GitHubClient._is_delegated_authored_pr(node, ""))


if __name__ == "__main__":
    unittest.main()
