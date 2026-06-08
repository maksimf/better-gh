import json
import unittest
from typing import Any

import httpx

from app.linear import LinearClient, LinearError, _pick_done_state


class _RecordingTransport(httpx.AsyncBaseTransport):
    """Captures every request and replies from a scripted queue."""

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
    responses: list[tuple[int, dict[str, Any] | str]],
    *,
    api_key: str = "lin_api_fake",
) -> tuple[LinearClient, _RecordingTransport]:
    transport = _RecordingTransport(responses)
    http = httpx.AsyncClient(transport=transport, base_url="https://example.invalid")
    client = LinearClient(api_key, http_client=http)
    return client, transport


def _issue_payload(
    *,
    current_state_id: str = "state-started",
    states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if states is None:
        states = [
            {"id": "state-started", "name": "In Progress", "type": "started", "position": 1.0},
            {"id": "state-done", "name": "Done", "type": "completed", "position": 2.0},
        ]
    return {
        "data": {
            "issue": {
                "id": "uuid-123",
                "identifier": "ENG-1234",
                "state": {
                    "id": current_state_id,
                    "name": "In Progress",
                    "type": "started",
                },
                "team": {"id": "team-1", "states": {"nodes": states}},
            }
        }
    }


class MarkIssueDoneTests(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_queries_then_updates(self) -> None:
        client, transport = _make_client(
            [
                (200, _issue_payload()),
                (
                    200,
                    {
                        "data": {
                            "issueUpdate": {
                                "success": True,
                                "issue": {
                                    "id": "uuid-123",
                                    "identifier": "ENG-1234",
                                    "state": {
                                        "id": "state-done",
                                        "name": "Done",
                                        "type": "completed",
                                    },
                                },
                            }
                        }
                    },
                ),
            ]
        )

        name = await client.mark_issue_done("ENG-1234")
        self.assertEqual(name, "Done")
        self.assertEqual(len(transport.requests), 2)

        # Personal API key rides verbatim -- no Bearer prefix.
        self.assertEqual(
            transport.requests[0].headers.get("Authorization"), "lin_api_fake"
        )
        update_body = json.loads(transport.requests[1].content.decode("utf-8"))
        self.assertEqual(
            update_body["variables"], {"id": "ENG-1234", "stateId": "state-done"}
        )
        await client.aclose()

    async def test_already_done_skips_update(self) -> None:
        client, transport = _make_client(
            [(200, _issue_payload(current_state_id="state-done"))]
        )
        name = await client.mark_issue_done("ENG-1234")
        self.assertEqual(name, "In Progress")  # echoes the current state name
        # No second (mutation) request fired.
        self.assertEqual(len(transport.requests), 1)
        await client.aclose()

    async def test_raises_without_api_key(self) -> None:
        client, _ = _make_client([], api_key="")
        with self.assertRaises(LinearError) as ctx:
            await client.mark_issue_done("ENG-1234")
        self.assertIn("LINEAR_API_KEY", str(ctx.exception))
        await client.aclose()

    async def test_raises_when_issue_missing(self) -> None:
        client, _ = _make_client([(200, {"data": {"issue": None}})])
        with self.assertRaises(LinearError) as ctx:
            await client.mark_issue_done("ENG-9999")
        self.assertIn("not found", str(ctx.exception))
        await client.aclose()

    async def test_raises_on_graphql_errors(self) -> None:
        client, _ = _make_client(
            [(200, {"errors": [{"message": "Invalid API key"}]})]
        )
        with self.assertRaises(LinearError) as ctx:
            await client.mark_issue_done("ENG-1234")
        self.assertIn("Invalid API key", str(ctx.exception))
        await client.aclose()

    async def test_raises_when_no_completed_state(self) -> None:
        states = [
            {"id": "s1", "name": "Todo", "type": "unstarted", "position": 1.0},
            {"id": "s2", "name": "In Progress", "type": "started", "position": 2.0},
        ]
        client, _ = _make_client([(200, _issue_payload(states=states))])
        with self.assertRaises(LinearError) as ctx:
            await client.mark_issue_done("ENG-1234")
        self.assertIn("completed", str(ctx.exception))
        await client.aclose()


class PickDoneStateTests(unittest.TestCase):
    def test_prefers_state_named_done(self) -> None:
        issue = {
            "team": {
                "states": {
                    "nodes": [
                        {"id": "a", "name": "Released", "type": "completed", "position": 1.0},
                        {"id": "b", "name": "Done", "type": "completed", "position": 9.0},
                    ]
                }
            }
        }
        self.assertEqual(_pick_done_state(issue)["id"], "b")

    def test_falls_back_to_lowest_position_completed(self) -> None:
        issue = {
            "team": {
                "states": {
                    "nodes": [
                        {"id": "a", "name": "Shipped", "type": "completed", "position": 5.0},
                        {"id": "b", "name": "Closed", "type": "completed", "position": 2.0},
                    ]
                }
            }
        }
        self.assertEqual(_pick_done_state(issue)["id"], "b")

    def test_returns_none_without_completed(self) -> None:
        issue = {"team": {"states": {"nodes": [{"id": "a", "type": "started"}]}}}
        self.assertIsNone(_pick_done_state(issue))


if __name__ == "__main__":
    unittest.main()
