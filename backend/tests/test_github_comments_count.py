"""Unit tests for ``GitHubClient._count_unresolved_comments``.

Covers both review-thread counting (including the viewer's / PR
author's own threads) and the behaviour where generic PR conversation
comments authored by humans count as "unresolved" unless the viewer
has left *any* emoji reaction on them. The ack check uses GitHub's
``reactionGroups.viewerHasReacted`` flag rather than the full reactor
list -- doing it the heavy way blew past GitHub's GraphQL node-count
limit and silently dropped PRs from the snapshot.
"""
from __future__ import annotations

import unittest

from app.github import GitHubClient


BOTS = frozenset({"cursor[bot]", "coderabbitai", "coderabbitai[bot]"})
VIEWER = "maksimf"


def _author(login: str, *, typename: str = "User") -> dict:
    """Match the ``author { __typename login }`` shape we query for."""
    return {"__typename": typename, "login": login}


def _thread(
    *, author: str, resolved: bool = False, typename: str = "User"
) -> dict:
    return {
        "isResolved": resolved,
        "comments": {
            "nodes": [{"author": _author(author, typename=typename), "body": "x"}]
        },
    }


_ALL_REACTION_CONTENTS = (
    "THUMBS_UP", "THUMBS_DOWN", "LAUGH", "HOORAY",
    "CONFUSED", "HEART", "ROCKET", "EYES",
)


def _reaction_groups(viewer_reacted_with: str | None = None) -> list[dict]:
    """Mirror GitHub's per-content reactionGroups payload.

    Every content type comes back, even with zero reactors. Pass a
    content string (e.g. ``"EYES"``, ``"THUMBS_UP"``) to mark that one
    as "viewer has reacted"; pass ``None`` for no viewer reactions.
    """
    return [
        {
            "content": c,
            "viewerHasReacted": (viewer_reacted_with == c),
        }
        for c in _ALL_REACTION_CONTENTS
    ]


def _comment(
    *,
    author: str,
    viewer_reacted_with: str | None = None,
    typename: str = "User",
) -> dict:
    """Build a generic PR conversation comment."""
    return {
        "author": _author(author, typename=typename),
        "body": "x",
        "reactionGroups": _reaction_groups(viewer_reacted_with=viewer_reacted_with),
    }


def _node(*, threads: list[dict] | None = None, comments: list[dict] | None = None) -> dict:
    return {
        "reviewThreads": {"nodes": threads or []},
        "comments": {"nodes": comments or []},
    }


class CountUnresolvedCommentsTests(unittest.TestCase):
    def test_unresolved_human_thread_is_counted(self) -> None:
        node = _node(threads=[_thread(author="alice")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_resolved_threads_are_ignored(self) -> None:
        node = _node(threads=[_thread(author="alice", resolved=True)])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 0))

    def test_bot_thread_buckets_into_bot(self) -> None:
        node = _node(threads=[_thread(author="coderabbitai", typename="Bot")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 1))

    def test_thread_authored_by_unknown_github_app_buckets_into_bot(self) -> None:
        # github-actions / vercel / dependabot etc. aren't in the static
        # BOT_LOGINS list -- the __typename check should still catch them.
        node = _node(
            threads=[_thread(author="github-actions", typename="Bot")]
        )

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 1))

    def test_generic_human_comment_without_eyes_counts_as_human(self) -> None:
        node = _node(comments=[_comment(author="alice")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_generic_human_comment_with_viewer_eyes_is_acked(self) -> None:
        node = _node(comments=[_comment(author="alice", viewer_reacted_with="EYES")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 0))

    def test_any_viewer_reaction_acks_the_comment(self) -> None:
        # Eyes is the canonical signal but anything works -- thumbs up,
        # heart, rocket, whatever. Verify a few representative reactions
        # all dismiss the comment.
        for content in ("THUMBS_UP", "HEART", "ROCKET", "HOORAY", "CONFUSED"):
            with self.subTest(content=content):
                node = _node(
                    comments=[
                        _comment(author="alice", viewer_reacted_with=content)
                    ]
                )

                human, bot = GitHubClient._count_unresolved_comments(
                    node, VIEWER, BOTS
                )

                self.assertEqual((human, bot), (0, 0))

    def test_viewers_own_generic_comment_counts_as_human(self) -> None:
        # PR author / viewer comments should show on the human chip.
        node = _node(comments=[_comment(author=VIEWER)])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_viewers_own_review_thread_counts_as_human(self) -> None:
        node = _node(threads=[_thread(author=VIEWER)])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_viewers_own_generic_comment_is_acked_by_reaction(self) -> None:
        node = _node(
            comments=[_comment(author=VIEWER, viewer_reacted_with="EYES")]
        )

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 0))

    def test_generic_bot_comment_is_not_counted(self) -> None:
        # The user explicitly only wanted human generic comments folded in;
        # bot conversation comments shouldn't bump either bucket here.
        node = _node(comments=[_comment(author="coderabbitai", typename="Bot")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (0, 0))

    def test_generic_github_app_comment_is_not_counted_as_human(self) -> None:
        # Regression: github-actions wasn't in BOT_LOGINS so its un-acked
        # status comment was leaking into the human count on PRs that
        # had it. Detect any GitHub App via __typename instead.
        node = _node(
            comments=[
                _comment(author="github-actions", typename="Bot"),
                _comment(author="nicoraga1"),
            ]
        )

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_third_party_reactions_do_not_ack(self) -> None:
        # All reactionGroups present with viewerHasReacted=False (someone
        # else reacted, but not the viewer). Comment should still count.
        node = _node(comments=[_comment(author="alice")])

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        self.assertEqual((human, bot), (1, 0))

    def test_threads_and_generic_comments_combine(self) -> None:
        node = _node(
            threads=[
                _thread(author="alice"),
                _thread(author="coderabbitai", typename="Bot"),
                _thread(author="bob", resolved=True),
                _thread(author=VIEWER),
            ],
            comments=[
                _comment(author="carol"),
                _comment(author="dave", viewer_reacted_with="EYES"),
                _comment(author="erin", viewer_reacted_with="THUMBS_UP"),
                _comment(author=VIEWER),
                _comment(author="cursor", typename="Bot"),
                _comment(author="github-actions", typename="Bot"),
            ],
        )

        human, bot = GitHubClient._count_unresolved_comments(node, VIEWER, BOTS)

        # alice thread + carol generic + VIEWER thread + VIEWER generic
        self.assertEqual((human, bot), (4, 1))


if __name__ == "__main__":
    unittest.main()
