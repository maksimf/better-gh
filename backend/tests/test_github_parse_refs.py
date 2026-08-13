"""``GitHubClient._parse_pr`` lifts ``baseRefName`` / ``headRefName``
straight onto ``PR.base_ref`` / ``PR.head_ref`` so the stack detector
can group PRs by head/base pairing.
"""
from __future__ import annotations

import unittest

from app.github import GitHubClient


def _node(**overrides: object) -> dict:
    """Minimal GraphQL ``PullRequest`` shape required by ``_parse_pr``."""
    node: dict = {
        "number": 42,
        "title": "Test PR",
        "url": "https://github.com/acme/web/pull/42",
        "body": "",
        "isDraft": False,
        "updatedAt": "2026-05-20T10:00:00Z",
        "author": {"login": "me"},
        "baseRepository": {"nameWithOwner": "acme/web"},
        "mergeable": "MERGEABLE",
        "commits": {"nodes": []},
        "reviewThreads": {"nodes": []},
        "reviewRequests": {"nodes": []},
        "latestReviews": {"nodes": []},
        "comments": {"nodes": []},
    }
    node.update(overrides)
    return node


class ParseRefsTests(unittest.TestCase):
    def _client(self) -> GitHubClient:
        return GitHubClient(
            token="t", graphql_url="https://example/graphql", max_prs=10
        )

    def test_parses_base_and_head_ref_names(self) -> None:
        pr = self._client()._parse_pr(
            _node(baseRefName="main", headRefName="feat/a")
        )
        self.assertEqual(pr.base_ref, "main")
        self.assertEqual(pr.head_ref, "feat/a")

    def test_missing_refs_default_to_empty_string(self) -> None:
        # Belt-and-braces: GitHub may occasionally omit fields on archived
        # branches; the PR model should still construct cleanly.
        pr = self._client()._parse_pr(_node())
        self.assertEqual(pr.base_ref, "")
        self.assertEqual(pr.head_ref, "")

    def test_parses_additions_and_deletions(self) -> None:
        pr = self._client()._parse_pr(
            _node(additions=120, deletions=45)
        )
        self.assertEqual(pr.additions, 120)
        self.assertEqual(pr.deletions, 45)

    def test_finds_github_uploaded_video_in_description(self) -> None:
        pr = self._client()._parse_pr(
            _node(
                body=(
                    "Demo:\n"
                    '<video src="https://github.com/user-attachments/assets/'
                    '123e4567-e89b-12d3-a456-426614174000"></video>'
                )
            )
        )
        self.assertEqual(
            pr.video_url,
            "https://github.com/user-attachments/assets/"
            "123e4567-e89b-12d3-a456-426614174000",
        )

    def test_finds_direct_and_embeddable_video_links(self) -> None:
        direct = self._client()._parse_pr(
            _node(body="[Demo](https://cdn.example.com/demo.webm?download=1)")
        )
        youtube = self._client()._parse_pr(
            _node(body="Watch https://youtu.be/dQw4w9WgXcQ?t=3")
        )
        self.assertEqual(
            direct.video_url, "https://cdn.example.com/demo.webm?download=1"
        )
        self.assertEqual(
            youtube.video_url, "https://youtu.be/dQw4w9WgXcQ?t=3"
        )

    def test_image_attachment_does_not_count_as_video(self) -> None:
        pr = self._client()._parse_pr(
            _node(
                body=(
                    "![Screenshot](https://github.com/user-attachments/assets/"
                    "123e4567-e89b-12d3-a456-426614174000)"
                )
            )
        )
        self.assertIsNone(pr.video_url)


if __name__ == "__main__":
    unittest.main()
