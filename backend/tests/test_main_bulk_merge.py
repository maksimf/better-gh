import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.auth import Session
from app.main import BulkMergeBody, BulkMergePr, app, bulk_merge_prs_endpoint


class BulkMergeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.http = httpx.AsyncClient()
        app.state.http_client = self.http

    async def asyncTearDown(self) -> None:
        await self.http.aclose()

    async def test_continues_after_failure_and_refreshes_once(self) -> None:
        gh = unittest.mock.Mock()
        gh.merge_pr = AsyncMock(
            side_effect=[{"merged": True}, RuntimeError("merge blocked")]
        )
        body = BulkMergeBody(
            prs=[
                BulkMergePr(owner="acme", repo="widgets", number=1),
                BulkMergePr(owner="acme", repo="widgets", number=2),
            ]
        )

        with patch("app.main.build_user_client", return_value=gh), patch(
            "app.main._safe_poll_once", new_callable=AsyncMock
        ) as safe_poll:
            response = await bulk_merge_prs_endpoint(
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
                    "number": 1,
                    "merged": True,
                    "error": None,
                },
                {
                    "owner": "acme",
                    "repo": "widgets",
                    "number": 2,
                    "merged": False,
                    "error": "merge blocked",
                },
            ],
        )
        self.assertEqual(gh.merge_pr.await_count, 2)
        safe_poll.assert_awaited_once_with("token", "alice")

    async def test_does_not_refresh_when_every_merge_fails(self) -> None:
        gh = unittest.mock.Mock()
        gh.merge_pr = AsyncMock(side_effect=RuntimeError("merge blocked"))
        body = BulkMergeBody(
            prs=[BulkMergePr(owner="acme", repo="widgets", number=1)]
        )

        with patch("app.main.build_user_client", return_value=gh), patch(
            "app.main._safe_poll_once", new_callable=AsyncMock
        ) as safe_poll:
            response = await bulk_merge_prs_endpoint(
                body,
                Session(token="token", login="alice"),
            )

        payload = json.loads(response.body)
        self.assertFalse(payload["results"][0]["merged"])
        safe_poll.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
