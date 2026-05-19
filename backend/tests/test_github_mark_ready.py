import json
import unittest
from typing import Any

import httpx

from app.github import GitHubClient


class _RecordingTransport(httpx.AsyncBaseTransport):
    """Captures every request and replies from a scripted queue.

    Mirrors the way the rest of the suite would mock httpx if it needed
    to: queue up (status_code, body) tuples, then drain them in order.
    """

    def __init__(self, responses: list[tuple[int, dict[str, Any] | str]]) -> None:
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
    responses: list[tuple[int, dict[str, Any] | str]]
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


class MarkPrReadyForReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_does_rest_lookup_then_graphql_mutation(self) -> None:
        client, transport = _make_client(
            [
                (200, {"node_id": "PR_kwDO_FAKE"}),
                (
                    200,
                    {
                        "data": {
                            "markPullRequestReadyForReview": {
                                "pullRequest": {"id": "PR_kwDO_FAKE", "isDraft": False}
                            }
                        }
                    },
                ),
            ]
        )

        await client.mark_pr_ready_for_review("acme", "widgets", 42)

        self.assertEqual(len(transport.requests), 2)

        rest_req = transport.requests[0]
        self.assertEqual(rest_req.method, "GET")
        self.assertEqual(
            str(rest_req.url),
            "https://api.github.com/repos/acme/widgets/pulls/42",
        )
        self.assertEqual(rest_req.headers.get("Authorization"), "bearer ghp_fake")

        gql_req = transport.requests[1]
        self.assertEqual(gql_req.method, "POST")
        self.assertEqual(str(gql_req.url), "https://api.github.com/graphql")
        body = json.loads(gql_req.content.decode("utf-8"))
        self.assertIn("markPullRequestReadyForReview", body["query"])
        self.assertEqual(body["variables"], {"id": "PR_kwDO_FAKE"})

        await client.aclose()

    async def test_raises_when_token_missing(self) -> None:
        client, _ = _make_client([])
        client._token = ""

        with self.assertRaises(RuntimeError) as ctx:
            await client.mark_pr_ready_for_review("acme", "widgets", 42)

        self.assertIn("GITHUB_TOKEN", str(ctx.exception))
        await client.aclose()

    async def test_raises_when_rest_lookup_fails(self) -> None:
        client, _ = _make_client([(404, "Not Found")])

        with self.assertRaises(RuntimeError) as ctx:
            await client.mark_pr_ready_for_review("acme", "widgets", 42)

        self.assertIn("404", str(ctx.exception))
        await client.aclose()

    async def test_raises_when_node_id_missing(self) -> None:
        client, _ = _make_client([(200, {"id": 1})])

        with self.assertRaises(RuntimeError) as ctx:
            await client.mark_pr_ready_for_review("acme", "widgets", 42)

        self.assertIn("node_id", str(ctx.exception))
        await client.aclose()

    async def test_raises_on_graphql_errors(self) -> None:
        client, _ = _make_client(
            [
                (200, {"node_id": "PR_kwDO_FAKE"}),
                (
                    200,
                    {
                        "errors": [
                            {"message": "Pull request is not in draft state."}
                        ]
                    },
                ),
            ]
        )

        with self.assertRaises(RuntimeError) as ctx:
            await client.mark_pr_ready_for_review("acme", "widgets", 42)

        self.assertIn("not in draft", str(ctx.exception))
        await client.aclose()


if __name__ == "__main__":
    unittest.main()
