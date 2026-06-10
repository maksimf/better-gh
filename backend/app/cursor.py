"""Minimal Cursor Cloud Agents API client for reading run state.

Each PR card can be linked to a cloud agent QAing the PR (the user pastes
the agent's ``https://cursor.com/agents/bc-...`` URL). This module reads
that agent's *current run* state so the card can show a "running" vs
"done" badge.

The Cloud Agents v1 API splits a durable *agent* from per-prompt *runs*:
execution status lives on the run, so we fetch the agent to find its
``latestRunId`` and then read that run's ``status`` (docs:
https://cursor.com/docs/cloud-agent/api/endpoints).

Auth is a server-wide API key (``settings.CURSOR_API_KEY``) sent as a
Bearer token. Like Linear, there's no per-viewer Cursor identity here, so
the key is shared across the deploy and the feature is off when unset.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("better_gh.cursor")

# Cursor run-status values, bucketed into the two states the UI cares
# about. Anything still in flight is "running"; any terminal status is
# "done" (the card stops polling once it sees one). Unknown/new statuses
# fall through to "unknown" so a future API addition degrades gracefully
# rather than being mislabelled as finished.
_RUNNING_STATUSES = frozenset(
    {"CREATING", "PENDING", "QUEUED", "RUNNING", "ACTIVE"}
)
_DONE_STATUSES = frozenset(
    {"FINISHED", "COMPLETED", "ERROR", "FAILED", "CANCELLED", "CANCELED", "EXPIRED"}
)


def classify_status(status: str | None) -> str:
    """Map a raw Cursor run status to ``running`` / ``done`` / ``unknown``."""
    if not status:
        return "unknown"
    upper = status.strip().upper()
    if upper in _RUNNING_STATUSES:
        return "running"
    if upper in _DONE_STATUSES:
        return "done"
    return "unknown"


class CursorError(RuntimeError):
    """Raised when a Cursor API call fails or returns no usable data."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CursorClient:
    """Tiny async Cursor Cloud Agents client scoped to reading run state."""

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.cursor.com",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str) -> dict[str, Any]:
        if not self._api_key:
            raise CursorError(
                "CURSOR_API_KEY is not configured; cannot read cloud agents."
            )
        resp = await self._client.get(
            f"{self._base_url}{path}",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
            },
        )
        if resp.status_code == 404:
            raise CursorError("Cloud agent not found.", status_code=404)
        if resp.status_code in (401, 403):
            raise CursorError(
                "Cursor rejected the API key (check CURSOR_API_KEY).",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            raise CursorError(
                f"Cursor returned {resp.status_code}: {resp.text}",
                status_code=resp.status_code,
            )
        body = resp.json()
        if not isinstance(body, dict):
            raise CursorError("Cursor response had an unexpected shape.")
        return body

    async def agent_run_state(self, agent_id: str) -> dict[str, Any]:
        """Read ``agent_id``'s latest-run state, normalised for the UI.

        Returns a dict with ``status`` (raw, e.g. ``RUNNING``/``FINISHED``),
        ``state`` (``running``/``done``/``unknown``), the canonical agent
        ``url``, the agent ``name``, and an optional ``pr_url`` lifted from
        the run's pushed branches. Raises :class:`CursorError` on failure.
        """
        agent_id = (agent_id or "").strip()
        if not agent_id:
            raise CursorError("No cloud agent id to look up.")

        agent = await self._get(f"/v1/agents/{agent_id}")
        agent_url = (
            agent.get("url") or f"https://cursor.com/agents/{agent_id}"
        )
        name = agent.get("name")
        run_id = agent.get("latestRunId")

        raw_status: str | None = None
        pr_url: str | None = None
        if isinstance(run_id, str) and run_id:
            run = await self._get(f"/v1/agents/{agent_id}/runs/{run_id}")
            raw_status = run.get("status")
            pr_url = _first_pr_url(run.get("git"))
        else:
            # No run yet -- fall back to the agent's own status so a freshly
            # created agent doesn't read as "unknown".
            raw_status = agent.get("status")

        return {
            "id": agent_id,
            "name": name,
            "status": raw_status,
            "state": classify_status(raw_status),
            "url": agent_url,
            "pr_url": pr_url,
        }


def _first_pr_url(git: object) -> str | None:
    """Pull the first pushed-branch PR URL out of a run's ``git`` block."""
    if not isinstance(git, dict):
        return None
    branches = git.get("branches")
    if not isinstance(branches, list):
        return None
    for branch in branches:
        if isinstance(branch, dict):
            pr_url = branch.get("prUrl")
            if isinstance(pr_url, str) and pr_url:
                return pr_url
    return None
