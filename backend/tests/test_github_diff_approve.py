import json
import unittest
from typing import Any

import httpx

from app.github import GitHubClient


class _RecordingTransport(httpx.AsyncBaseTransport):
    """Captures every request and replies from a scripted queue."""

    def __init__(self, responses: list[tuple[int, dict[str, Any] | list | str]]) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(
                f"Unexpected extra request to {request.method} {request.url}"
            )
        status, body = self._responses.pop(0)
        if isinstance(body, (dict, list)):
            content = json.dumps(body).encode("utf-8")
            headers = {"Content-Type": "application/json"}
        else:
            content = body.encode("utf-8")
            headers = {"Content-Type": "text/plain"}
        return httpx.Response(status, content=content, headers=headers)


def _make_client(
    responses: list[tuple[int, dict[str, Any] | list | str]]
) -> tuple[GitHubClient, _RecordingTransport]:
    transport = _RecordingTransport(responses)
    http = httpx.AsyncClient(transport=transport, base_url="https://example.invalid")
    client = GitHubClient(
        token="ghp_fake",
        graphql_url="https://api.github.com/graphql",
        api_url="https://api.github.com",
        max_prs=1,
        http_client=http,
    )
    return client, transport


class FetchPrDiffTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_normalized_files(self) -> None:
        client, transport = _make_client(
            [
                (
                    200,
                    [
                        {
                            "filename": "app/main.py",
                            "status": "modified",
                            "additions": 3,
                            "deletions": 1,
                            "patch": "@@ -1 +1,3 @@\n-old\n+new\n+more",
                        },
                        {
                            "filename": "assets/logo.png",
                            "status": "added",
                            "additions": 0,
                            "deletions": 0,
                            # GitHub omits `patch` for binaries.
                        },
                    ],
                ),
            ]
        )

        files = await client.fetch_pr_diff("acme", "widgets", 42)

        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["filename"], "app/main.py")
        self.assertEqual(files[0]["additions"], 3)
        self.assertEqual(files[0]["patch"], "@@ -1 +1,3 @@\n-old\n+new\n+more")
        self.assertIsNone(files[1]["patch"])

        req = transport.requests[0]
        self.assertEqual(req.method, "GET")
        self.assertIn(
            "/repos/acme/widgets/pulls/42/files", str(req.url)
        )
        self.assertEqual(req.headers.get("Authorization"), "bearer ghp_fake")
        await client.aclose()

    async def test_paginates_until_short_page(self) -> None:
        full_page = [
            {
                "filename": f"file{i}.py",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "patch": "@@ -0,0 +1 @@\n+x",
            }
            for i in range(100)
        ]
        client, transport = _make_client(
            [
                (200, full_page),
                (200, [{"filename": "last.py", "status": "added"}]),
            ]
        )

        files = await client.fetch_pr_diff("acme", "widgets", 7)

        self.assertEqual(len(files), 101)
        self.assertEqual(len(transport.requests), 2)
        self.assertIn("page=1", str(transport.requests[0].url))
        self.assertIn("page=2", str(transport.requests[1].url))
        await client.aclose()

    async def test_raises_when_token_missing(self) -> None:
        client, _ = _make_client([])
        client._token = ""

        with self.assertRaises(RuntimeError) as ctx:
            await client.fetch_pr_diff("acme", "widgets", 42)

        self.assertIn("access token", str(ctx.exception))
        await client.aclose()

    async def test_raises_on_http_error(self) -> None:
        client, _ = _make_client([(404, "Not Found")])

        with self.assertRaises(RuntimeError) as ctx:
            await client.fetch_pr_diff("acme", "widgets", 42)

        self.assertIn("404", str(ctx.exception))
        await client.aclose()


class FetchPrDetailsTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_body_and_head_sha(self) -> None:
        client, transport = _make_client(
            [
                (
                    200,
                    {
                        "body": "## Summary\nDoes a thing.",
                        "head": {"sha": "abc123"},
                    },
                )
            ]
        )

        details = await client.fetch_pr_details("acme", "widgets", 42)

        self.assertEqual(details["body"], "## Summary\nDoes a thing.")
        self.assertEqual(details["head_sha"], "abc123")
        req = transport.requests[0]
        self.assertEqual(req.method, "GET")
        self.assertEqual(
            str(req.url), "https://api.github.com/repos/acme/widgets/pulls/42"
        )
        await client.aclose()

    async def test_returns_none_when_body_empty(self) -> None:
        client, _ = _make_client([(200, {"body": "", "head": {"sha": "abc"}})])

        details = await client.fetch_pr_details("acme", "widgets", 42)
        self.assertIsNone(details["body"])
        self.assertEqual(details["head_sha"], "abc")
        await client.aclose()

    async def test_returns_none_when_body_and_sha_missing(self) -> None:
        client, _ = _make_client([(200, {"number": 42})])

        details = await client.fetch_pr_details("acme", "widgets", 42)
        self.assertIsNone(details["body"])
        self.assertIsNone(details["head_sha"])
        await client.aclose()

    async def test_fetch_pr_body_wrapper(self) -> None:
        client, _ = _make_client(
            [(200, {"body": "hi", "head": {"sha": "abc"}})]
        )

        self.assertEqual(await client.fetch_pr_body("acme", "widgets", 42), "hi")
        await client.aclose()

    async def test_raises_when_token_missing(self) -> None:
        client, _ = _make_client([])
        client._token = ""

        with self.assertRaises(RuntimeError) as ctx:
            await client.fetch_pr_details("acme", "widgets", 42)

        self.assertIn("access token", str(ctx.exception))
        await client.aclose()

    async def test_raises_on_http_error(self) -> None:
        client, _ = _make_client([(404, "Not Found")])

        with self.assertRaises(RuntimeError) as ctx:
            await client.fetch_pr_details("acme", "widgets", 42)

        self.assertIn("404", str(ctx.exception))
        await client.aclose()


class SubmitReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_approve_event(self) -> None:
        client, transport = _make_client([(200, {"id": 1, "state": "APPROVED"})])

        await client.approve_pr("acme", "widgets", 42)

        req = transport.requests[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(
            str(req.url),
            "https://api.github.com/repos/acme/widgets/pulls/42/reviews",
        )
        body = json.loads(req.content.decode("utf-8"))
        self.assertEqual(body["event"], "APPROVE")
        self.assertNotIn("body", body)
        await client.aclose()

    async def test_posts_request_changes(self) -> None:
        client, transport = _make_client([(200, {"id": 1})])

        await client.submit_review(
            "acme", "widgets", 42, "REQUEST_CHANGES", body="Please fix"
        )

        body = json.loads(transport.requests[0].content.decode("utf-8"))
        self.assertEqual(body["event"], "REQUEST_CHANGES")
        self.assertEqual(body["body"], "Please fix")
        await client.aclose()

    async def test_posts_comment_event(self) -> None:
        client, transport = _make_client([(200, {"id": 1})])

        await client.submit_review("acme", "widgets", 42, "COMMENT", body="nits")

        body = json.loads(transport.requests[0].content.decode("utf-8"))
        self.assertEqual(body["event"], "COMMENT")
        self.assertEqual(body["body"], "nits")
        await client.aclose()

    async def test_includes_body_when_provided(self) -> None:
        client, transport = _make_client([(200, {"id": 1})])

        await client.approve_pr("acme", "widgets", 42, body="  LGTM  ")

        body = json.loads(transport.requests[0].content.decode("utf-8"))
        self.assertEqual(body["body"], "LGTM")
        await client.aclose()

    async def test_raises_when_token_missing(self) -> None:
        client, _ = _make_client([])
        client._token = ""

        with self.assertRaises(RuntimeError) as ctx:
            await client.submit_review("acme", "widgets", 42, "APPROVE")

        self.assertIn("access token", str(ctx.exception))
        await client.aclose()

    async def test_raises_on_http_error(self) -> None:
        client, _ = _make_client(
            [(422, "Can not approve your own pull request")]
        )

        with self.assertRaises(RuntimeError) as ctx:
            await client.approve_pr("acme", "widgets", 42)

        self.assertIn("422", str(ctx.exception))
        await client.aclose()


class PostReviewCommentTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_single_line_comment(self) -> None:
        client, transport = _make_client([(201, {"id": 99})])

        await client.post_review_comment(
            "acme",
            "widgets",
            42,
            commit_id="abc123",
            path="app/main.py",
            body="nit",
            line=10,
            side="RIGHT",
        )

        req = transport.requests[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(
            str(req.url),
            "https://api.github.com/repos/acme/widgets/pulls/42/comments",
        )
        body = json.loads(req.content.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "body": "nit",
                "commit_id": "abc123",
                "path": "app/main.py",
                "line": 10,
                "side": "RIGHT",
            },
        )
        await client.aclose()

    async def test_posts_multi_line_comment(self) -> None:
        client, transport = _make_client([(201, {"id": 99})])

        await client.post_review_comment(
            "acme",
            "widgets",
            42,
            commit_id="abc123",
            path="app/main.py",
            body="range nit",
            line=15,
            side="RIGHT",
            start_line=10,
            start_side="RIGHT",
        )

        body = json.loads(transport.requests[0].content.decode("utf-8"))
        self.assertEqual(body["start_line"], 10)
        self.assertEqual(body["start_side"], "RIGHT")
        self.assertEqual(body["line"], 15)
        await client.aclose()

    async def test_raises_on_http_error(self) -> None:
        client, _ = _make_client([(422, "Validation Failed")])

        with self.assertRaises(RuntimeError) as ctx:
            await client.post_review_comment(
                "acme",
                "widgets",
                42,
                commit_id="abc",
                path="a.py",
                body="x",
                line=1,
                side="RIGHT",
            )

        self.assertIn("422", str(ctx.exception))
        await client.aclose()


if __name__ == "__main__":
    unittest.main()
