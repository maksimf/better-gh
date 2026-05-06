"""GitHub GraphQL client for the viewer's open PRs."""
from __future__ import annotations

import logging
from typing import Any, Iterable

import httpx

from .config import settings
from .model import PR, Checks
from .preview import extract_preview_url

log = logging.getLogger("better_gh.github")

QUERY = """
query MyOpenPRs($first: Int!, $assignedQuery: String!) {
  viewer {
    login
    pullRequests(
      first: $first
      states: OPEN
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes { ...prFields }
    }
  }
  assignedToMe: search(first: $first, type: ISSUE, query: $assignedQuery) {
    nodes { ... on PullRequest { ...prFields } }
  }
}

fragment prFields on PullRequest {
  number
  title
  url
  isDraft
  updatedAt
  author { login }
  baseRepository { nameWithOwner }
  mergeable
  commits(last: 1) {
    nodes {
      commit {
        statusCheckRollup {
          contexts(first: 100) {
            nodes {
              __typename
              ... on CheckRun     { name status conclusion }
              ... on StatusContext { context state }
            }
          }
        }
      }
    }
  }
  reviewThreads(first: 100) {
    nodes {
      isResolved
      comments(first: 1) { nodes { author { login } body } }
    }
  }
  reviewRequests(first: 50) {
    nodes {
      requestedReviewer {
        __typename
        ... on User { login }
      }
    }
  }
  latestReviews(first: 50) {
    nodes {
      state
      author { login }
    }
  }
  comments(first: 100) { nodes { author { login } body } }
}
""".strip()

_ASSIGNED_QUERY = "is:pr is:open assignee:@me sort:updated-desc archived:false"


_PASS_CHECK_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_PENDING_CHECK_STATUSES = {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED"}
_FAIL_CHECK_CONCLUSIONS = {
    "FAILURE",
    "TIMED_OUT",
    "CANCELLED",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
    "STALE",
}

_PASS_STATUS_STATES = {"SUCCESS", "EXPECTED"}
_PENDING_STATUS_STATES = {"PENDING"}
_FAIL_STATUS_STATES = {"FAILURE", "ERROR"}


class GitHubClient:
    """Async GitHub GraphQL client tuned for our single-query use case."""

    def __init__(
        self,
        token: str,
        graphql_url: str,
        max_prs: int,
        *,
        api_url: str = "https://api.github.com",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self._graphql_url = graphql_url
        self._api_url = api_url.rstrip("/")
        self._max_prs = max_prs
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def merge_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        method: str = "merge",
    ) -> dict[str, Any]:
        """Merge a PR via ``PUT /repos/{owner}/{repo}/pulls/{n}/merge``.

        ``method`` is one of ``merge`` / ``squash`` / ``rebase``. Raises on
        HTTP error so the caller can surface 405 (not mergeable) etc.
        Returns the parsed JSON body on success.
        """
        if not self._token:
            raise RuntimeError("GITHUB_TOKEN is not set; cannot merge PRs.")
        url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}/merge"
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.put(
            url, headers=headers, json={"merge_method": method}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} when merging "
                f"{owner}/{repo}#{pr_number} ({method}): {resp.text}"
            )
        return resp.json() if resp.content else {}

    async def request_reviewer(
        self, owner: str, repo: str, pr_number: int, reviewer_login: str
    ) -> None:
        """Add ``reviewer_login`` to the requested-reviewers of a PR.

        Wraps ``POST /repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers``.
        Raises on HTTP error so the caller can surface the failure.
        """
        if not self._token:
            raise RuntimeError("GITHUB_TOKEN is not set; cannot request reviewers.")
        url = (
            f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            "/requested_reviewers"
        )
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.post(
            url, headers=headers, json={"reviewers": [reviewer_login]}
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} when requesting "
                f"@{reviewer_login} on {owner}/{repo}#{pr_number}: {resp.text}"
            )

    async def fetch_open_prs(self) -> list[PR]:
        """Open PRs the viewer authored OR is assigned to (deduped, recent-first)."""
        if not self._token:
            raise RuntimeError(
                "GITHUB_TOKEN is not set; cannot query the GitHub GraphQL API."
            )

        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        payload = {
            "query": QUERY,
            "variables": {
                "first": self._max_prs,
                "assignedQuery": _ASSIGNED_QUERY,
            },
        }
        resp = await self._client.post(self._graphql_url, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()

        if body.get("errors"):
            raise RuntimeError(f"GitHub GraphQL errors: {body['errors']}")

        data = body.get("data") or {}
        authored = (
            (((data.get("viewer") or {}).get("pullRequests") or {}).get("nodes")) or []
        )
        assigned = ((data.get("assignedToMe") or {}).get("nodes")) or []

        seen: set[str] = set()
        prs: list[PR] = []
        for node in (*authored, *assigned):
            if not node or not node.get("number") or not node.get("url"):
                continue
            url = node["url"]
            if url in seen:
                continue
            seen.add(url)
            prs.append(self._parse_pr(node))

        prs.sort(key=lambda p: p.updated_at, reverse=True)
        return prs

    def _parse_pr(self, node: dict[str, Any]) -> PR:
        author = (node.get("author") or {}).get("login") or "unknown"
        repo = (node.get("baseRepository") or {}).get("nameWithOwner") or "unknown/unknown"

        checks = self._extract_checks(node)
        comments_human, comments_bot = self._count_unresolved_comments(node)
        preview_url = self._find_preview(node)
        conflicts = self._extract_conflicts(node)
        review_requested = self._is_review_requested(node)
        approved_by_reviewer = self._is_approved_by_reviewer(node)

        return PR(
            number=int(node.get("number") or 0),
            title=node.get("title") or "",
            url=node.get("url") or "",
            repo=repo,
            author=author,
            is_draft=bool(node.get("isDraft")),
            checks=checks,
            comments_human=comments_human,
            comments_bot=comments_bot,
            preview_url=preview_url,
            conflicts=conflicts,
            updated_at=node.get("updatedAt") or "",
            review_requested=review_requested,
            approved_by_reviewer=approved_by_reviewer,
        )

    def _extract_checks(self, node: dict[str, Any]) -> Checks:
        commit_nodes = ((node.get("commits") or {}).get("nodes")) or []
        if not commit_nodes:
            return Checks()
        rollup = ((commit_nodes[0] or {}).get("commit") or {}).get("statusCheckRollup")
        if not rollup:
            return Checks()
        contexts = ((rollup.get("contexts") or {}).get("nodes")) or []

        passed = pending = failed = 0
        for ctx in contexts:
            if not ctx:
                continue
            bucket = self._classify_context(ctx)
            if bucket == "passed":
                passed += 1
            elif bucket == "pending":
                pending += 1
            elif bucket == "failed":
                failed += 1
        return Checks(passed=passed, pending=pending, failed=failed)

    @staticmethod
    def _classify_context(ctx: dict[str, Any]) -> str:
        typename = ctx.get("__typename")
        if typename == "CheckRun":
            status = (ctx.get("status") or "").upper()
            conclusion = (ctx.get("conclusion") or "").upper()
            if status != "COMPLETED":
                if status in _PENDING_CHECK_STATUSES or status == "":
                    return "pending"
                return "pending"
            if conclusion in _PASS_CHECK_CONCLUSIONS:
                return "passed"
            if conclusion in _FAIL_CHECK_CONCLUSIONS:
                return "failed"
            return "failed"
        if typename == "StatusContext":
            state = (ctx.get("state") or "").upper()
            if state in _PASS_STATUS_STATES:
                return "passed"
            if state in _PENDING_STATUS_STATES:
                return "pending"
            if state in _FAIL_STATUS_STATES:
                return "failed"
            return "failed"
        return "passed"

    def _count_unresolved_comments(
        self, node: dict[str, Any]
    ) -> tuple[int, int]:
        threads = ((node.get("reviewThreads") or {}).get("nodes")) or []
        bot_logins = settings.BOT_LOGINS
        human = bot = 0
        for thread in threads:
            if not thread or thread.get("isResolved"):
                continue
            comments = ((thread.get("comments") or {}).get("nodes")) or []
            login = ""
            if comments and comments[0]:
                author = comments[0].get("author") or {}
                login = (author.get("login") or "").lower()
            if login and login in bot_logins:
                bot += 1
            else:
                human += 1
        return human, bot

    def _find_preview(self, node: dict[str, Any]) -> str | None:
        prefix = settings.PREVIEW_COMMENT_PREFIX
        for body in self._iter_comment_bodies(node):
            url = extract_preview_url(body, prefix)
            if url:
                return url
        return None

    @staticmethod
    def _iter_comment_bodies(node: dict[str, Any]) -> Iterable[str]:
        comments = ((node.get("comments") or {}).get("nodes")) or []
        for c in comments:
            if c and c.get("body"):
                yield c["body"]
        threads = ((node.get("reviewThreads") or {}).get("nodes")) or []
        for thread in threads:
            if not thread:
                continue
            for c in ((thread.get("comments") or {}).get("nodes")) or []:
                if c and c.get("body"):
                    yield c["body"]

    def _is_approved_by_reviewer(self, node: dict[str, Any]) -> bool:
        """Whether ``settings.REVIEWER_LOGIN``'s most recent review is APPROVED."""
        target = (settings.REVIEWER_LOGIN or "").lower()
        if not target:
            return False
        nodes = ((node.get("latestReviews") or {}).get("nodes")) or []
        for r in nodes:
            if not r:
                continue
            login = ((r.get("author") or {}).get("login") or "").lower()
            if login != target:
                continue
            return (r.get("state") or "").upper() == "APPROVED"
        return False

    def _is_review_requested(self, node: dict[str, Any]) -> bool:
        """Whether ``settings.REVIEWER_LOGIN`` is on the requested-reviewers list."""
        target = (settings.REVIEWER_LOGIN or "").lower()
        if not target:
            return False
        nodes = ((node.get("reviewRequests") or {}).get("nodes")) or []
        for r in nodes:
            if not r:
                continue
            reviewer = r.get("requestedReviewer") or {}
            if reviewer.get("__typename") != "User":
                continue
            login = (reviewer.get("login") or "").lower()
            if login == target:
                return True
        return False

    def _extract_conflicts(self, node: dict[str, Any]) -> int:
        mergeable = (node.get("mergeable") or "").upper()
        if mergeable == "CONFLICTING":
            return 1
        if mergeable == "UNKNOWN":
            log.warning(
                "PR #%s mergeable state is UNKNOWN; treating as 0 conflicts",
                node.get("number"),
            )
        return 0
