"""GitHub GraphQL client for the viewer's open PRs."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable, Mapping

import httpx

from .config import settings
from .model import PR, Checks, FailedCheck, ReviewPR
from .preview import extract_preview_url

log = logging.getLogger("better_gh.github")

_COMMENTS_QUERY = """
query PrHumanComments($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes {
              databaseId
              author { login __typename }
              body
              url
              reactionGroups { content viewerHasReacted }
            }
          }
        }
      }
      comments(first: 100) {
        nodes {
          databaseId
          author { login __typename }
          body
          url
          reactionGroups { content viewerHasReacted }
        }
      }
    }
  }
}
""".strip()


class GitHubRateLimitError(RuntimeError):
    """Raised when GitHub returns a primary or secondary rate-limit error.

    ``reset_at`` is parsed from response headers (``X-RateLimit-Reset`` for
    primary limits, ``Retry-After`` for secondary limits). It may be
    ``None`` if neither header is present or parseable; callers should only
    surface a "try again at..." hint when this is set.
    """

    def __init__(self, message: str, *, reset_at: datetime | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


def _parse_rate_limit_reset(headers: Mapping[str, str]) -> datetime | None:
    """Pick the most authoritative reset timestamp out of GitHub's headers.

    Prefers ``X-RateLimit-Reset`` (UNIX epoch seconds) since it's an absolute
    instant. Falls back to ``Retry-After`` (delta-seconds or HTTP-date). All
    parse failures are swallowed -- the banner just hides the time hint
    rather than showing nonsense.
    """
    reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")
    if reset:
        try:
            return datetime.fromtimestamp(int(reset), tz=timezone.utc)
        except (TypeError, ValueError):
            pass

    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after:
        retry_after = retry_after.strip()
        if retry_after.isdigit():
            return datetime.now(timezone.utc) + timedelta(seconds=int(retry_after))
        try:
            parsed = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError):
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


QUERY = """
query DashboardSnapshot(
  $first: Int!,
  $assignedQuery: String!,
  $reviewRequestedQuery: String!
) {
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
  reviewRequested: search(first: $first, type: ISSUE, query: $reviewRequestedQuery) {
    nodes { ... on PullRequest { ...slimReviewFields } }
  }
  rateLimit { cost limit remaining resetAt }
}

fragment prFields on PullRequest {
  number
  title
  url
  body
  additions
  deletions
  isDraft
  updatedAt
  baseRefName
  headRefName
  author { login }
  assignees(first: 10) { nodes { login } }
  baseRepository { nameWithOwner }
  mergeable
  commits(last: 1) {
    nodes {
      commit {
        statusCheckRollup {
          contexts(first: 100) {
            nodes {
              __typename
              ... on CheckRun     { name status conclusion detailsUrl }
              ... on StatusContext { context state targetUrl }
            }
          }
        }
      }
    }
  }
  reviewThreads(first: 100) {
    nodes {
      isResolved
      comments(first: 1) { nodes { author { __typename login } body } }
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
  comments(first: 100) {
    nodes {
      author { __typename login }
      body
      reactionGroups { content viewerHasReacted }
    }
  }
}

fragment slimReviewFields on PullRequest {
  number
  title
  url
  additions
  deletions
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
              ... on CheckRun     { name status conclusion detailsUrl }
              ... on StatusContext { context state targetUrl }
            }
          }
        }
      }
    }
  }
  timelineItems(itemTypes: [REVIEW_REQUESTED_EVENT], last: 50) {
    nodes {
      ... on ReviewRequestedEvent {
        createdAt
        requestedReviewer {
          __typename
          ... on User { login }
        }
      }
    }
  }
  reviews(first: 50) {
    nodes {
      state
      submittedAt
      author { login }
    }
  }
}
""".strip()

_ASSIGNED_QUERY = "is:pr is:open assignee:@me sort:updated-desc archived:false"
# We deliberately don't add ``-reviewed-by:@me`` here. GitHub's
# ``review-requested:USER`` qualifier already matches the *current*
# requested-reviewers list, and submitting an APPROVED/CHANGES_REQUESTED
# review removes you from it -- so "PRs I've already reviewed" naturally
# fall off until the author re-requests you. ``-reviewed-by:@me`` is
# permanent ("ever submitted any review on this PR") and was over-eager:
# any re-requested PR you'd previously commented on disappeared, even
# though the author wants another look.
_REVIEW_REQUESTED_QUERY = (
    "is:pr is:open review-requested:@me sort:updated-desc archived:false"
)


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


def _compile_linear_pattern(prefix: str) -> re.Pattern[str] | None:
    """Compile ``\\b<prefix>\\d{3,}\\b`` for the configured ticket prefix.

    Returns ``None`` when the prefix is empty -- callers should treat that
    as "Linear linking disabled" rather than guessing a default.
    """
    if not prefix:
        return None
    return re.compile(rf"\b{re.escape(prefix)}(\d{{3,}})\b")


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
            raise RuntimeError("No GitHub access token on session; cannot merge PRs.")
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

    async def mark_pr_ready_for_review(
        self, owner: str, repo: str, pr_number: int
    ) -> None:
        """Flip a draft PR to "Ready for review".

        GitHub doesn't expose this via REST -- the only path is the
        ``markPullRequestReadyForReview`` GraphQL mutation, which needs
        the PR's global node id. We grab that id via the REST pulls
        endpoint (cheap, single GET) and then fire the mutation, instead
        of caching the node id on every PR in the snapshot.
        """
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot mark PRs ready for review."
            )
        rest_url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        get_resp = await self._client.get(rest_url, headers=headers)
        if get_resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {get_resp.status_code} when looking up "
                f"{owner}/{repo}#{pr_number}: {get_resp.text}"
            )
        node_id = (get_resp.json() or {}).get("node_id")
        if not node_id:
            raise RuntimeError(
                f"GitHub didn't return a node_id for {owner}/{repo}#{pr_number}"
            )

        mutation = (
            "mutation MarkReady($id: ID!) {"
            " markPullRequestReadyForReview(input: {pullRequestId: $id}) {"
            " pullRequest { id isDraft } } }"
        )
        gql_headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        gql_resp = await self._client.post(
            self._graphql_url,
            headers=gql_headers,
            json={"query": mutation, "variables": {"id": node_id}},
        )
        if gql_resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {gql_resp.status_code} when marking "
                f"{owner}/{repo}#{pr_number} ready for review: {gql_resp.text}"
            )
        body = gql_resp.json() or {}
        if body.get("errors"):
            raise RuntimeError(
                f"GitHub GraphQL errors marking {owner}/{repo}#{pr_number} "
                f"ready for review: {body['errors']}"
            )

    async def request_reviewers(
        self, owner: str, repo: str, pr_number: int, reviewer_logins: list[str]
    ) -> None:
        """Add ``reviewer_logins`` to the requested-reviewers of a PR.

        Wraps ``POST /repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers``,
        which already accepts a list of logins in one call. Raises on HTTP
        error so the caller can surface the failure. A no-op when the list
        is empty (nothing to request).
        """
        if not reviewer_logins:
            return
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot request reviewers."
            )
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
            url, headers=headers, json={"reviewers": reviewer_logins}
        )
        if resp.status_code >= 400:
            joined = ", ".join(f"@{r}" for r in reviewer_logins)
            raise RuntimeError(
                f"GitHub returned {resp.status_code} when requesting "
                f"{joined} on {owner}/{repo}#{pr_number}: {resp.text}"
            )

    async def search_users(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        """Search GitHub users by login/name for the reviewer autocomplete.

        Wraps ``GET /search/users?q={query} type:user``. Proxied through the
        backend so the viewer's OAuth token never reaches the browser.
        Returns a slim ``[{login, avatar_url, name}]`` list (name is only
        present on GitHub's detailed user payloads, so it's left ``None``
        here -- the search endpoint doesn't return it). Raises on HTTP error.
        """
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot search users."
            )
        url = f"{self._api_url}/search/users"
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        params = {
            "q": f"{query} type:user",
            "per_page": str(max(1, min(limit, 25))),
        }
        resp = await self._client.get(url, headers=headers, params=params)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} searching users "
                f"for {query!r}: {resp.text}"
            )
        body = resp.json() or {}
        items = body.get("items") or []
        out: list[dict[str, Any]] = []
        for item in items:
            login = item.get("login")
            if not login:
                continue
            out.append(
                {
                    "login": login,
                    "avatar_url": item.get("avatar_url") or "",
                }
            )
        return out

    async def fetch_human_comments(
        self,
        owner: str,
        repo: str,
        number: int,
        viewer_login: str,
        bot_logins: frozenset[str] | set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch unresolved human comments on a PR for the comments popover.

        Returns a list of ``{id, type, author, body, url}`` dicts where
        ``type`` is ``"review"`` (inline review-thread) or ``"issue"``
        (general PR conversation comment). Mirrors the filtering logic
        in :meth:`_count_unresolved_comments` so the popover items match
        the displayed count exactly.
        """
        bots = bot_logins if bot_logins is not None else frozenset()
        viewer = (viewer_login or "").lower()

        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(
            self._graphql_url,
            headers=headers,
            json={
                "query": _COMMENTS_QUERY,
                "variables": {"owner": owner, "repo": repo, "number": number},
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise RuntimeError(
                f"GitHub GraphQL errors fetching comments: {body['errors']}"
            )

        pr = (
            ((body.get("data") or {}).get("repository") or {})
            .get("pullRequest") or {}
        )

        def _is_bot(author: dict[str, Any] | None) -> bool:
            if not author:
                return False
            if (author.get("__typename") or "") == "Bot":
                return True
            login = (author.get("login") or "").lower()
            return bool(login and login in bots)

        out: list[dict[str, Any]] = []

        threads = ((pr.get("reviewThreads") or {}).get("nodes")) or []
        for thread in threads:
            if not thread or thread.get("isResolved"):
                continue
            comments = ((thread.get("comments") or {}).get("nodes")) or []
            if not comments or not comments[0]:
                continue
            c = comments[0]
            author = c.get("author") or {}
            login = (author.get("login") or "").lower()
            if viewer and login == viewer:
                continue
            if _is_bot(author):
                continue
            out.append(
                {
                    "id": c.get("databaseId"),
                    "type": "review",
                    "author": author.get("login") or "unknown",
                    "body": c.get("body") or "",
                    "url": c.get("url") or "",
                }
            )

        generic = ((pr.get("comments") or {}).get("nodes")) or []
        for c in generic:
            if not c:
                continue
            author = c.get("author") or {}
            login = (author.get("login") or "").lower()
            if not login:
                continue
            if _is_bot(author):
                continue
            if viewer and login == viewer:
                continue
            groups = c.get("reactionGroups") or []
            acked = any(g and g.get("viewerHasReacted") for g in groups)
            if acked:
                continue
            out.append(
                {
                    "id": c.get("databaseId"),
                    "type": "issue",
                    "author": author.get("login") or "unknown",
                    "body": c.get("body") or "",
                    "url": c.get("url") or "",
                }
            )

        return out

    async def add_comment_reaction(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        comment_type: str,
        content: str = "eyes",
    ) -> None:
        """Add a reaction to a PR comment (review or issue-style)."""
        if comment_type == "review":
            url = (
                f"{self._api_url}/repos/{owner}/{repo}"
                f"/pulls/comments/{comment_id}/reactions"
            )
        else:
            url = (
                f"{self._api_url}/repos/{owner}/{repo}"
                f"/issues/comments/{comment_id}/reactions"
            )
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.post(url, headers=headers, json={"content": content})
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} adding reaction "
                f"to {owner}/{repo} comment {comment_id}: {resp.text}"
            )

    async def post_issue_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
    ) -> None:
        """Post a new issue-style comment on a PR (used for quoted replies)."""
        url = f"{self._api_url}/repos/{owner}/{repo}/issues/{number}/comments"
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.post(url, headers=headers, json={"body": body})
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} posting comment "
                f"on {owner}/{repo}#{number}: {resp.text}"
            )

    async def fetch_pr_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        *,
        max_files: int = 300,
    ) -> list[dict[str, Any]]:
        """Fetch a PR's per-file diffs for the read-only review panel.

        Wraps ``GET /repos/{owner}/{repo}/pulls/{n}/files`` (paginated,
        100 per page) and returns one dict per changed file:
        ``{filename, status, additions, deletions, patch, previous_filename}``.
        ``patch`` is GitHub's unified-diff hunk text, or ``None`` for files
        GitHub doesn't diff inline (binaries, very large files). We cap at
        ``max_files`` so a monster PR can't balloon the response.
        """
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot fetch PR diffs."
            )
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            url = (
                f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
                f"?per_page=100&page={page}"
            )
            resp = await self._client.get(url, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"GitHub returned {resp.status_code} fetching files for "
                    f"{owner}/{repo}#{pr_number}: {resp.text}"
                )
            batch = resp.json() or []
            for f in batch:
                if not f:
                    continue
                files.append(
                    {
                        "filename": f.get("filename") or "",
                        "status": f.get("status") or "modified",
                        "additions": int(f.get("additions") or 0),
                        "deletions": int(f.get("deletions") or 0),
                        "patch": f.get("patch"),
                        "previous_filename": f.get("previous_filename"),
                    }
                )
            if len(batch) < 100 or len(files) >= max_files:
                break
            page += 1
        return files[:max_files]

    async def approve_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str = "",
    ) -> None:
        """Submit an APPROVE review on a PR.

        Wraps ``POST /repos/{owner}/{repo}/pulls/{n}/reviews`` with
        ``event: APPROVE``. ``body`` is an optional review summary comment.
        Raises on HTTP error so the caller can surface GitHub's reason
        (e.g. 422 when you try to approve your own PR).
        """
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot approve PRs."
            )
        url = f"{self._api_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        headers = {
            "Authorization": f"bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload: dict[str, Any] = {"event": "APPROVE"}
        if body.strip():
            payload["body"] = body.strip()
        resp = await self._client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub returned {resp.status_code} approving "
                f"{owner}/{repo}#{pr_number}: {resp.text}"
            )

    async def fetch_dashboard_snapshot(
        self,
    ) -> tuple[list[PR], list[ReviewPR], dict[str, Any] | None]:
        """One GraphQL POST that returns everything the dashboard needs.

        Combines the viewer's authored + assigned PRs (rich fields for the
        main board) with the review-requested search (slim fields for the
        "Reviewing" tab) and the ``rateLimit`` block, so a single round
        trip costs ~one query's worth of GraphQL points instead of two.
        Returns ``(my_prs, review_prs, rate_limit)`` -- ``rate_limit`` is
        the raw dict (``cost``/``limit``/``remaining``/``resetAt``) or
        ``None`` if GitHub omitted it.
        """
        if not self._token:
            raise RuntimeError(
                "No GitHub access token on session; cannot query the GitHub GraphQL API."
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
                "reviewRequestedQuery": _REVIEW_REQUESTED_QUERY,
            },
        }
        resp = await self._client.post(
            self._graphql_url, headers=headers, json=payload
        )

        if resp.status_code == 429 or resp.status_code == 403:
            reset_at = _parse_rate_limit_reset(resp.headers)
            raise GitHubRateLimitError(
                f"GitHub rate limit hit ({resp.status_code}).",
                reset_at=reset_at,
            )

        resp.raise_for_status()
        body = resp.json()

        if body.get("errors"):
            errors = body["errors"]
            if any((e or {}).get("type") == "RATE_LIMITED" for e in errors):
                reset_at = _parse_rate_limit_reset(resp.headers)
                raise GitHubRateLimitError(
                    "GitHub API rate limit exceeded.",
                    reset_at=reset_at,
                )
            raise RuntimeError(f"GitHub GraphQL errors: {errors}")

        data = body.get("data") or {}
        viewer = data.get("viewer") or {}
        viewer_login = (viewer.get("login") or "").lower()
        authored = ((viewer.get("pullRequests") or {}).get("nodes")) or []
        assigned = ((data.get("assignedToMe") or {}).get("nodes")) or []
        review_nodes = ((data.get("reviewRequested") or {}).get("nodes")) or []

        seen: set[str] = set()
        prs: list[PR] = []
        for node in (*authored, *assigned):
            if not node or not node.get("number") or not node.get("url"):
                continue
            url = node["url"]
            if url in seen:
                continue
            seen.add(url)
            if self._is_delegated_authored_pr(node, viewer_login):
                # Viewer opened the PR but explicitly handed it off via
                # assignees -- someone else owns driving it forward, so
                # it shouldn't clutter the viewer's personal queue.
                continue
            if self._viewer_already_approved(node, viewer_login):
                # Viewer has already signed off (APPROVED) on this PR --
                # hide it regardless of who authored it. Typically catches
                # PRs the viewer is assigned to but has already approved;
                # GitHub blocks self-approval so authored PRs are unaffected.
                continue
            prs.append(self._parse_pr(node, viewer_login))
        prs.sort(key=lambda p: p.updated_at, reverse=True)

        review_prs: list[ReviewPR] = []
        review_seen: set[str] = set()
        for node in review_nodes:
            if not node or not node.get("number") or not node.get("url"):
                continue
            url = node["url"]
            if url in review_seen:
                continue
            review_seen.add(url)
            if self._viewer_review_resolved(node, viewer_login):
                # Viewer already submitted APPROVED/CHANGES_REQUESTED after
                # the latest visible request, so treat this one as handled.
                # If the author re-requests review later, it should show up
                # again.
                continue
            review_prs.append(self._parse_review_pr(node, viewer_login))
        # Sort by request time (most recent first); fall back to updated_at
        # so PRs missing a request timestamp don't sort to the very top.
        review_prs.sort(
            key=lambda p: (p.requested_at or p.updated_at), reverse=True
        )

        rate_limit = data.get("rateLimit")
        return prs, review_prs, rate_limit

    def _parse_review_pr(
        self, node: dict[str, Any], viewer_login: str
    ) -> ReviewPR:
        repo = (node.get("baseRepository") or {}).get(
            "nameWithOwner"
        ) or "unknown/unknown"
        author = (node.get("author") or {}).get("login") or "unknown"
        requested_at = self._latest_request_for_viewer(node, viewer_login)
        return ReviewPR(
            number=int(node.get("number") or 0),
            title=node.get("title") or "",
            url=node.get("url") or "",
            repo=repo,
            author=author,
            is_draft=bool(node.get("isDraft")),
            checks=self._extract_checks(node),
            conflicts=self._extract_conflicts(node),
            updated_at=node.get("updatedAt") or "",
            requested_at=requested_at,
            additions=max(0, int(node.get("additions") or 0)),
            deletions=max(0, int(node.get("deletions") or 0)),
        )

    @staticmethod
    def _is_delegated_authored_pr(
        node: dict[str, Any], viewer_login: str
    ) -> bool:
        """Did the viewer open this PR and then delegate it via assignees?

        Returns ``True`` when the viewer is the author *and* the PR has
        at least one assignee but the viewer isn't among them -- i.e.
        someone else is the named owner now. PRs with no assignees are
        kept (viewer is still implicitly on the hook), and PRs where the
        viewer is one of several assignees are kept (they're still
        on the hook explicitly).
        """
        if not viewer_login:
            return False
        author = ((node.get("author") or {}).get("login") or "").lower()
        if author != viewer_login:
            return False
        assignee_nodes = ((node.get("assignees") or {}).get("nodes")) or []
        assignee_logins: list[str] = []
        for a in assignee_nodes:
            if not a:
                continue
            login = (a.get("login") or "").lower()
            if login:
                assignee_logins.append(login)
        if not assignee_logins:
            return False
        return viewer_login not in assignee_logins

    @staticmethod
    def _latest_request_for_viewer(
        node: dict[str, Any], viewer_login: str
    ) -> str:
        """ISO timestamp of the most recent ReviewRequestedEvent for viewer.

        Returns an empty string when the timeline window we fetched
        doesn't include a request targeting the viewer (e.g. they were
        added so long ago that the last 50 review-request events have
        scrolled past it). The caller should treat empty as "unknown".
        """
        if not viewer_login:
            return ""
        events = (
            (node.get("timelineItems") or {}).get("nodes")
        ) or []
        latest = ""
        for evt in events:
            if not evt:
                continue
            reviewer = evt.get("requestedReviewer") or {}
            if reviewer.get("__typename") != "User":
                continue
            login = (reviewer.get("login") or "").lower()
            if login != viewer_login:
                continue
            created = evt.get("createdAt") or ""
            if created > latest:
                latest = created
        return latest

    @classmethod
    def _viewer_review_resolved(
        cls, node: dict[str, Any], viewer_login: str
    ) -> bool:
        """Has the viewer handled the latest visible request for this PR?

        "Substantive" means at least one submitted review by the viewer
        with state APPROVED or CHANGES_REQUESTED. Plain COMMENTED
        reviews don't count (those are drive-by notes; the author still
        expects a real verdict).

        APPROVED is treated as a permanent dismiss: once the viewer has
        signed off, the PR stays hidden even if the author re-requests
        review later -- the user's stance is "I'm done with this".

        For CHANGES_REQUESTED a later review request is genuine new work
        (the author likely addressed feedback and wants another look),
        so we only treat the PR as resolved while no fresher request has
        landed. When the timeline window doesn't include the request
        timestamp, stay conservative and keep showing the PR rather than
        silently dropping a requested review.
        """
        if not viewer_login:
            return False
        review_at, review_state = cls._latest_substantive_review_for_viewer(
            node, viewer_login
        )
        if not review_at:
            return False
        if review_state == "APPROVED":
            return True
        latest_request = cls._latest_request_for_viewer(node, viewer_login)
        if not latest_request:
            return False
        return review_at >= latest_request

    @staticmethod
    def _latest_substantive_review_for_viewer(
        node: dict[str, Any], viewer_login: str
    ) -> tuple[str, str]:
        """ISO timestamp + state of viewer's latest APPROVED/CHANGES_REQUESTED review.

        Returns ``("", "")`` when the viewer has no substantive review.
        The state lets callers distinguish "approved" from "asked for
        changes" without re-walking the reviews list.
        """
        if not viewer_login:
            return "", ""
        reviews = ((node.get("reviews") or {}).get("nodes")) or []
        latest_at = ""
        latest_state = ""
        for r in reviews:
            if not r:
                continue
            login = ((r.get("author") or {}).get("login") or "").lower()
            if login != viewer_login:
                continue
            state = (r.get("state") or "").upper()
            if state not in ("APPROVED", "CHANGES_REQUESTED"):
                continue
            submitted = r.get("submittedAt") or ""
            if submitted > latest_at:
                latest_at = submitted
                latest_state = state
        return latest_at, latest_state

    @staticmethod
    def _viewer_already_approved(
        node: dict[str, Any], viewer_login: str
    ) -> bool:
        """Has the viewer's most recent review on this PR been APPROVED?

        Reads ``latestReviews`` (one entry per reviewer, the freshest
        each has submitted), so this naturally goes false if the viewer
        later switched to CHANGES_REQUESTED. Used to hide PRs from the
        main board that the viewer has already signed off on -- typically
        PRs they're assigned to but have approved.
        """
        if not viewer_login:
            return False
        nodes = ((node.get("latestReviews") or {}).get("nodes")) or []
        for r in nodes:
            if not r:
                continue
            login = ((r.get("author") or {}).get("login") or "").lower()
            if login != viewer_login:
                continue
            return (r.get("state") or "").upper() == "APPROVED"
        return False

    def _parse_pr(self, node: dict[str, Any], viewer_login: str = "") -> PR:
        author = (node.get("author") or {}).get("login") or "unknown"
        repo = (node.get("baseRepository") or {}).get("nameWithOwner") or "unknown/unknown"

        checks = self._extract_checks(node)
        comments_human, comments_bot = self._count_unresolved_comments(
            node, viewer_login, settings.BOT_LOGINS
        )
        preview_url = self._find_preview(node)
        conflicts = self._extract_conflicts(node)
        requested_reviewers = self._extract_requested_reviewers(node)
        approver_logins = self._extract_approver_logins(node)
        linear_url = self._find_linear_url(node)

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
            requested_reviewers=requested_reviewers,
            approver_logins=approver_logins,
            linear_url=linear_url,
            base_ref=node.get("baseRefName") or "",
            head_ref=node.get("headRefName") or "",
            additions=max(0, int(node.get("additions") or 0)),
            deletions=max(0, int(node.get("deletions") or 0)),
        )

    @staticmethod
    def _find_linear_url(node: dict[str, Any]) -> str | None:
        """Extract the first ``<PREFIX><digits>`` ticket ref from title/body.

        Title wins over body so authors can override what shows up by
        editing the title -- typical convention is to lead with the
        ticket id anyway. Returns ``None`` when the prefix is unset or
        no ticket reference is found.
        """
        prefix = settings.LINEAR_TICKET_PREFIX
        pattern = _compile_linear_pattern(prefix)
        if pattern is None:
            return None
        base = (settings.LINEAR_WORKSPACE_URL or "").rstrip("/")
        if not base:
            return None
        for text in (node.get("title") or "", node.get("body") or ""):
            match = pattern.search(text)
            if match:
                return f"{base}/issue/{prefix}{match.group(1)}"
        return None

    def _extract_checks(self, node: dict[str, Any]) -> Checks:
        commit_nodes = ((node.get("commits") or {}).get("nodes")) or []
        if not commit_nodes:
            return Checks()
        rollup = ((commit_nodes[0] or {}).get("commit") or {}).get("statusCheckRollup")
        if not rollup:
            return Checks()
        contexts = ((rollup.get("contexts") or {}).get("nodes")) or []

        passed = pending = failed = 0
        failed_names: list[FailedCheck] = []
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
                failed_names.append(self._failed_check_from_context(ctx))
        # Sort by name so the popover order is stable across polls --
        # GitHub's contexts list isn't deterministic, and unstable order
        # would force the card to re-render on every poll via the
        # fingerprint even when nothing actually changed.
        failed_names.sort(key=lambda f: (f.name.lower(), f.url or ""))
        return Checks(
            passed=passed,
            pending=pending,
            failed=failed,
            failed_names=tuple(failed_names),
        )

    @staticmethod
    def _failed_check_from_context(ctx: dict[str, Any]) -> FailedCheck:
        """Pull the human-readable name + details URL off a failing context.

        CheckRun has ``name`` + ``detailsUrl``; StatusContext has
        ``context`` + ``targetUrl``. Either field may be missing on
        weird third-party reporters -- we fall back to a placeholder
        name and ``None`` URL rather than dropping the entry.
        """
        typename = ctx.get("__typename")
        if typename == "CheckRun":
            return FailedCheck(
                name=(ctx.get("name") or "(unnamed check)").strip()
                or "(unnamed check)",
                url=(ctx.get("detailsUrl") or None),
            )
        if typename == "StatusContext":
            return FailedCheck(
                name=(ctx.get("context") or "(unnamed status)").strip()
                or "(unnamed status)",
                url=(ctx.get("targetUrl") or None),
            )
        return FailedCheck(name="(unknown check)", url=None)

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

    @staticmethod
    def _count_unresolved_comments(
        node: dict[str, Any],
        viewer_login: str = "",
        bot_logins: frozenset[str] | set[str] | None = None,
    ) -> tuple[int, int]:
        """Count unresolved review threads + un-acked generic human comments.

        Review-thread counts work like before: each unresolved thread
        becomes one tally, bucketed by the thread-opener's login --
        except threads opened by the viewer themselves are skipped
        (you shouldn't have to clear notes you left for yourself).

        Generic (issue-style) PR conversation comments add to the human
        count when *all* of these hold: the author is a real human (not
        a bot, not the viewer themselves), and the viewer hasn't left
        *any* emoji reaction on it. Any reaction works -- thumbs up,
        eyes, rocket, heart, whatever -- because the only thing we care
        about is "did the viewer click *something*". We rely on
        GitHub's ``reactionGroups.viewerHasReacted`` for the ack check
        (cheap, server-side) instead of pulling every reactor list,
        which kept the GraphQL response under GitHub's node-count
        limit. Bot conversation comments are intentionally not folded
        in here so the bot chip keeps its existing meaning (unresolved
        review-thread bot comments only).

        "Bot" means either ``author.__typename == "Bot"`` (which covers
        every GitHub App -- ``github-actions``, ``vercel``,
        ``dependabot``, etc. -- without us having to enumerate them) or
        a login explicitly listed in ``bot_logins`` (escape hatch for
        regular User accounts the user wants treated as bots).
        """
        bots = bot_logins if bot_logins is not None else frozenset()
        viewer = (viewer_login or "").lower()

        def _is_bot(author: dict[str, Any] | None) -> bool:
            if not author:
                return False
            if (author.get("__typename") or "") == "Bot":
                return True
            login = (author.get("login") or "").lower()
            return bool(login and login in bots)

        human = bot = 0

        threads = ((node.get("reviewThreads") or {}).get("nodes")) or []
        for thread in threads:
            if not thread or thread.get("isResolved"):
                continue
            comments = ((thread.get("comments") or {}).get("nodes")) or []
            author = (comments[0].get("author") if comments and comments[0] else None)
            login = ((author or {}).get("login") or "").lower()
            if viewer and login == viewer:
                continue
            if _is_bot(author):
                bot += 1
            else:
                human += 1

        generic = ((node.get("comments") or {}).get("nodes")) or []
        for c in generic:
            if not c:
                continue
            author = c.get("author") or {}
            login = (author.get("login") or "").lower()
            if not login:
                continue
            if _is_bot(author):
                continue
            if viewer and login == viewer:
                continue
            groups = c.get("reactionGroups") or []
            acked = any(g and g.get("viewerHasReacted") for g in groups)
            if not acked:
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

    @staticmethod
    def _extract_approver_logins(node: dict[str, Any]) -> tuple[str, ...]:
        """Logins whose most recent review on this PR is APPROVED.

        Reviewer-agnostic on purpose: the per-viewer "is *my* tracked
        reviewer in here" check lives in
        :meth:`app.model.PR.is_approved_by` so the same parsed PR can
        be cached once and rendered for any viewer.
        """
        nodes = ((node.get("latestReviews") or {}).get("nodes")) or []
        out: list[str] = []
        seen: set[str] = set()
        for r in nodes:
            if not r:
                continue
            login = ((r.get("author") or {}).get("login") or "").strip()
            if not login:
                continue
            if (r.get("state") or "").upper() != "APPROVED":
                continue
            key = login.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(login)
        return tuple(out)

    @staticmethod
    def _extract_requested_reviewers(node: dict[str, Any]) -> tuple[str, ...]:
        """Logins currently on the PR's requested-reviewers list (Users only).

        Teams are intentionally skipped: the per-card "Request review"
        button + the R chip both speak in terms of a specific user
        login.
        """
        nodes = ((node.get("reviewRequests") or {}).get("nodes")) or []
        out: list[str] = []
        seen: set[str] = set()
        for r in nodes:
            if not r:
                continue
            reviewer = r.get("requestedReviewer") or {}
            if reviewer.get("__typename") != "User":
                continue
            login = (reviewer.get("login") or "").strip()
            if not login:
                continue
            key = login.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(login)
        return tuple(out)

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
