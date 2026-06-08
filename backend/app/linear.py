"""Minimal Linear GraphQL client for marking an issue done.

The dashboard already detects a Linear ticket reference inside a PR's
title/body and renders a per-card link (see
``GitHubClient._find_linear_url``). This module adds the one *write*
operation we need: moving a ticket into its team's "completed" workflow
state when the user merges the PR.

Auth is a server-wide personal API key (``settings.LINEAR_API_KEY``).
Unlike GitHub -- where every viewer rides their own OAuth token -- there
is no per-user Linear identity here, so the key is shared across the
deploy and the feature is simply off when it's unset.

Linear's GraphQL API accepts the human-readable identifier (e.g.
``ENG-1234``) anywhere an issue ``id`` is expected, so we never have to
resolve the UUID ourselves. Personal API keys go in the ``Authorization``
header verbatim -- *no* ``Bearer`` prefix.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("better_gh.linear")

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"

# Workflow-state category that means "this issue is finished". Linear's
# state ``type`` enum is one of: triage, backlog, unstarted, started,
# completed, canceled. "Done" is the canonical name but teams rename it,
# so we match on the stable ``type`` instead.
_COMPLETED_STATE_TYPE = "completed"

_ISSUE_QUERY = """
query IssueStates($id: String!) {
  issue(id: $id) {
    id
    identifier
    state { id name type }
    team {
      id
      states { nodes { id name type position } }
    }
  }
}
"""

_UPDATE_MUTATION = """
mutation MarkDone($id: String!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
    issue { id identifier state { id name type } }
  }
}
"""


class LinearError(RuntimeError):
    """Raised when a Linear API call fails or returns no usable data."""


class LinearClient:
    """Tiny async Linear client scoped to the mark-done use case."""

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        graphql_url: str = LINEAR_GRAPHQL_URL,
    ) -> None:
        self._api_key = api_key
        self._graphql_url = graphql_url
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key:
            raise LinearError(
                "LINEAR_API_KEY is not configured; cannot update Linear issues."
            )
        resp = await self._client.post(
            self._graphql_url,
            headers={
                # Personal API keys are sent verbatim -- NOT as a Bearer token.
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )
        if resp.status_code >= 400:
            raise LinearError(
                f"Linear returned {resp.status_code}: {resp.text}"
            )
        body = resp.json() or {}
        if body.get("errors"):
            raise LinearError(f"Linear GraphQL errors: {body['errors']}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise LinearError("Linear response had no data.")
        return data

    async def mark_issue_done(self, identifier: str) -> str:
        """Move ``identifier`` (e.g. ``ENG-1234``) into its team's done state.

        Returns the name of the state the issue landed in. Raises
        :class:`LinearError` if the issue can't be found, the team has no
        completed-type state, or the update is rejected.
        """
        identifier = (identifier or "").strip()
        if not identifier:
            raise LinearError("No Linear ticket identifier to update.")

        data = await self._post(_ISSUE_QUERY, {"id": identifier})
        issue = data.get("issue")
        if not isinstance(issue, dict):
            raise LinearError(f"Linear issue {identifier!r} not found.")

        target = _pick_done_state(issue)
        if target is None:
            raise LinearError(
                f"No completed workflow state found for {identifier!r}'s team."
            )

        # Already done? Skip the write and report the current state.
        current = issue.get("state") or {}
        if current.get("id") == target["id"]:
            return str(current.get("name") or target.get("name") or "Done")

        result = await self._post(
            _UPDATE_MUTATION, {"id": identifier, "stateId": target["id"]}
        )
        update = result.get("issueUpdate") or {}
        if not update.get("success"):
            raise LinearError(f"Linear rejected the update for {identifier!r}.")
        updated_state = (update.get("issue") or {}).get("state") or {}
        return str(updated_state.get("name") or target.get("name") or "Done")


def _pick_done_state(issue: dict[str, Any]) -> dict[str, Any] | None:
    """Choose the completed-type workflow state for the issue's team.

    Teams can define more than one ``completed`` state (e.g. "Done" and
    "Released"); prefer one literally named "Done", otherwise the
    lowest-``position`` completed state so we land in the canonical
    finish line rather than a downstream archive bucket.
    """
    team = issue.get("team") or {}
    nodes = ((team.get("states") or {}).get("nodes")) or []
    completed = [
        s for s in nodes if (s.get("type") or "").lower() == _COMPLETED_STATE_TYPE
    ]
    if not completed:
        return None
    for state in completed:
        if (state.get("name") or "").strip().lower() == "done":
            return state
    return min(completed, key=lambda s: s.get("position") or 0)
