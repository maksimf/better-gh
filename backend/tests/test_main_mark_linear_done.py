import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app import state
from app.main import _mark_linear_done_for_pr
from app.model import Checks, PR
from app.state import Snapshot


def _pr_with_linear(*, repo: str, number: int, linear_url: str) -> PR:
    return PR(
        number=number,
        title="Test PR",
        url=f"https://github.com/{repo}/pull/{number}",
        repo=repo,
        author="alice",
        is_draft=False,
        checks=Checks(),
        comments_human=0,
        comments_bot=0,
        preview_url="https://preview.example.com",
        conflicts=0,
        updated_at="2026-01-01T00:00:00Z",
        linear_url=linear_url,
    )


class MarkLinearDoneForPrTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefers_client_provided_ticket_over_snapshot_lookup(self) -> None:
        http = httpx.AsyncClient()
        try:
            with patch("app.main.settings.LINEAR_API_KEY", "lin_api_fake"), patch(
                "app.main.LinearClient"
            ) as mocked_client:
                mocked_client.return_value.mark_issue_done = AsyncMock(return_value="Done")
                done, error = await _mark_linear_done_for_pr(
                    "alice",
                    "acme",
                    "widgets",
                    42,
                    http,
                    linear_ticket=" eng-1234 ",
                )

            self.assertTrue(done)
            self.assertIsNone(error)
            mocked_client.return_value.mark_issue_done.assert_awaited_once_with("ENG-1234")
        finally:
            await http.aclose()

    async def test_falls_back_to_snapshot_when_no_client_ticket(self) -> None:
        login = "alice-fallback"
        await state.set_snapshot(
            login,
            Snapshot(
                prs=[
                    _pr_with_linear(
                        repo="acme/widgets",
                        number=99,
                        linear_url="https://linear.app/acme/issue/ENG-9999/some-title",
                    )
                ]
            ),
        )

        http = httpx.AsyncClient()
        try:
            with patch("app.main.settings.LINEAR_API_KEY", "lin_api_fake"), patch(
                "app.main.LinearClient"
            ) as mocked_client:
                mocked_client.return_value.mark_issue_done = AsyncMock(return_value="Done")
                done, error = await _mark_linear_done_for_pr(
                    login,
                    "acme",
                    "widgets",
                    99,
                    http,
                )

            self.assertTrue(done)
            self.assertIsNone(error)
            mocked_client.return_value.mark_issue_done.assert_awaited_once_with("ENG-9999")
        finally:
            await state.drop_user(login)
            await http.aclose()


if __name__ == "__main__":
    unittest.main()
