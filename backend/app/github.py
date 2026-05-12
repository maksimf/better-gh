"""GitHub GraphQL client for the viewer's open PRs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable, Mapping

import httpx

from .config import settings
from .model import PR, Checks, ReviewPR
from .preview import extract_preview_url

log = logging.getLogger("better_gh.github")


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
  isDraft
  updatedAt
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

fragment slimReviewFields on PullRequest {
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
            prs.append(self._parse_pr(node))
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
                # Viewer already submitted APPROVED/CHANGES_REQUESTED and
                # hasn't been re-requested since -- treat as "done with
                # this one" even though GitHub still surfaces it via
                # ``review-requested:@me`` (e.g. team-level requests or
                # CODEOWNERS rules can keep the entry alive).
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
        """Has the viewer ever delivered a substantive verdict on this PR?

        "Substantive" means at least one submitted review by the viewer
        with state APPROVED or CHANGES_REQUESTED. Plain COMMENTED
        reviews don't count (those are drive-by notes; the author still
        expects a real verdict).

        We deliberately ignore re-request events here. GitHub's
        ``latestReviews`` flips your old review back to "pending" when
        the author hits "Re-request review", so we'd never see your
        prior verdict; and even when we *can* see a re-request after
        your verdict, the user has told us they consider their job
        done. The re-request will still surface that PR in this query
        result -- the filter below is what hides it.
        """
        if not viewer_login:
            return False
        reviews = ((node.get("reviews") or {}).get("nodes")) or []
        for r in reviews:
            if not r:
                continue
            login = ((r.get("author") or {}).get("login") or "").lower()
            if login != viewer_login:
                continue
            state = (r.get("state") or "").upper()
            if state in ("APPROVED", "CHANGES_REQUESTED"):
                return True
        return False

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
