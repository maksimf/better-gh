import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.auth import Session
from app.main import BulkMergePr, StackMergeBody, app, stack_merge_prs_endpoint


class StackMergeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.http = httpx.AsyncClient()
        app.state.http_client = self.http
        self.calls: list[tuple[str, tuple]] = []

    async def asyncTearDown(self) -> None:
        await self.http.aclose()

    def _gh(self, merge_side_effect=None) -> unittest.mock.Mock:
        gh = unittest.mock.Mock()

        async def get_pr(owner, repo, number):
            self.calls.append(("get", (owner, repo, number)))
            return {"base": {"ref": "main"}}

        async def update_pr_base(owner, repo, number, base):
            self.calls.append(("retarget", (owner, repo, number, base)))

        async def merge_pr(owner, repo, number, method="merge"):
            self.calls.append(("merge", (owner, repo, number)))
            if merge_side_effect is not None:
                result = merge_side_effect.pop(0)
                if isinstance(result, Exception):
                    raise result
                return result
            return {"merged": True}

        gh.get_pr = AsyncMock(side_effect=get_pr)
        gh.update_pr_base = AsyncMock(side_effect=update_pr_base)
        gh.merge_pr = AsyncMock(side_effect=merge_pr)
        return gh

    async def test_merges_root_then_child_retargeting_to_root_base(self) -> None:
        gh = self._gh()
        body = StackMergeBody(
            prs=[
                BulkMergePr(owner="acme", repo="widgets", number=10),
                BulkMergePr(owner="acme", repo="widgets", number=11),
            ]
        )

        with patch("app.main.build_user_client", return_value=gh), patch(
            "app.main._safe_poll_once", new_callable=AsyncMock
        ) as safe_poll:
            response = await stack_merge_prs_endpoint(
                body,
                Session(token="token", login="alice"),
            )

        payload = json.loads(response.body)
        self.assertEqual(
            payload["results"],
            [
                {
                    "owner": "acme",
                    "repo": "widgets",
                    "number": 10,
                    "merged": True,
                    "error": None,
                },
                {
                    "owner": "acme",
                    "repo": "widgets",
                    "number": 11,
                    "merged": True,
                    "error": None,
                },
            ],
        )
        self.assertEqual(
            self.calls,
            [
                ("get", ("acme", "widgets", 10)),
                ("merge", ("acme", "widgets", 10)),
                ("retarget", ("acme", "widgets", 11, "main")),
                ("merge", ("acme", "widgets", 11)),
            ],
        )
        safe_poll.assert_awaited_once_with("token", "alice")

    async def test_stops_after_first_failed_merge(self) -> None:
        gh = self._gh(
            merge_side_effect=[
                {"merged": True},
                RuntimeError("merge blocked"),
                {"merged": True},
            ]
        )
        body = StackMergeBody(
            prs=[
                BulkMergePr(owner="acme", repo="widgets", number=10),
                BulkMergePr(owner="acme", repo="widgets", number=11),
                BulkMergePr(owner="acme", repo="widgets", number=12),
            ]
        )

        with patch("app.main.build_user_client", return_value=gh), patch(
            "app.main._safe_poll_once", new_callable=AsyncMock
        ) as safe_poll:
            response = await stack_merge_prs_endpoint(
                body,
                Session(token="token", login="alice"),
            )

        payload = json.loads(response.body)
        self.assertEqual(
            [item["number"] for item in payload["results"]],
            [10, 11, 12],
        )
        self.assertTrue(payload["results"][0]["merged"])
        self.assertFalse(payload["results"][1]["merged"])
        self.assertEqual(payload["results"][1]["error"], "merge blocked")
        self.assertFalse(payload["results"][2]["merged"])
        self.assertEqual(
            payload["results"][2]["error"],
            "skipped: earlier stack PR failed",
        )
        self.assertEqual(
            [call[0] for call in self.calls],
            ["get", "merge", "retarget", "merge"],
        )
        self.assertNotIn(("merge", ("acme", "widgets", 12)), self.calls)
        safe_poll.assert_awaited_once_with("token", "alice")

    async def test_does_not_refresh_when_root_cannot_be_read(self) -> None:
        gh = unittest.mock.Mock()
        gh.get_pr = AsyncMock(side_effect=RuntimeError("not found"))
        gh.update_pr_base = AsyncMock()
        gh.merge_pr = AsyncMock()
        body = StackMergeBody(
            prs=[
                BulkMergePr(owner="acme", repo="widgets", number=10),
                BulkMergePr(owner="acme", repo="widgets", number=11),
            ]
        )

        with patch("app.main.build_user_client", return_value=gh), patch(
            "app.main._safe_poll_once", new_callable=AsyncMock
        ) as safe_poll:
            response = await stack_merge_prs_endpoint(
                body,
                Session(token="token", login="alice"),
            )

        payload = json.loads(response.body)
        self.assertFalse(payload["results"][0]["merged"])
        self.assertEqual(payload["results"][0]["error"], "not found")
        gh.merge_pr.assert_not_awaited()
        gh.update_pr_base.assert_not_awaited()
        safe_poll.assert_not_awaited()
