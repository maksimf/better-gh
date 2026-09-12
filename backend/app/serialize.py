"""Serialize the in-memory snapshot into the JSON the React SPA consumes.

The React board needs per-viewer derived state (which column a PR lands
in, whether the tracked reviewer approved / was requested, and the
stack layout) so it doesn't have to re-implement the column rules from
:mod:`app.model` / :mod:`app.stack` in TypeScript. We compute those here
using the exact same model methods the old Jinja templates did, keeping
one source of truth for the readiness / column logic.

The reviewer is supplied per request (the client owns it in
localStorage and sends it as a query param) so the cached snapshot can
stay reviewer-agnostic and be shared across every viewer.
"""
from __future__ import annotations

from datetime import datetime

from .config import settings
from .model import PR, ReviewPR
from .stack import attach_stacks


def _split_logins(raw: str) -> list[str]:
    """Parse a comma-separated login list into ordered, deduped logins."""
    seen: set[str] = set()
    out: list[str] = []
    for part in raw.split(","):
        login = part.strip().lower()
        if login and login not in seen:
            seen.add(login)
            out.append(login)
    return out


def effective_reviewers(reviewers_param: str | None) -> list[str]:
    """Resolve the set of reviewer logins a serialization should track.

    Three-tier fallback so the per-viewer override layers cleanly on
    top of the deploy-wide default. ``reviewers_param`` is a
    comma-separated list of logins sent by the client:

    * ``None`` -> use ``settings.REVIEWER_LOGIN`` (the "I haven't
      configured anything; show the default reviewer(s)" case). The env
      default may itself be comma-separated.
    * Empty string -> ``[]`` (the explicit "track nobody, hide the
      chips" case -- distinct from "unset").
    * Anything else -> the parsed, trimmed, lower-cased, deduped logins.
    """
    if reviewers_param is None:
        return _split_logins(settings.REVIEWER_LOGIN or "")
    return _split_logins(reviewers_param)


def _serialize_checks(pr_checks) -> dict[str, object]:
    return {
        "passed": pr_checks.passed,
        "pending": pr_checks.pending,
        "failed": pr_checks.failed,
        "failed_names": [
            {"name": c.name, "url": c.url} for c in pr_checks.failed_names
        ],
    }


def _serialize_stack_nodes(
    pr: PR | ReviewPR, reviewers: list[str]
) -> list[dict[str, object]]:
    if pr.stack is None:
        return []
    return [
        {
            "number": node.number,
            "title": node.title,
            "url": node.url,
            "depth": node.depth,
            "column": node.column_for(reviewers),
            "is_self": node.number == pr.number,
        }
        for node in pr.stack.nodes
    ]


def serialize_pr(pr: PR, reviewers: list[str]) -> dict[str, object]:
    stack_id = (
        f"{pr.repo}#{pr.stack.nodes[0].number}" if pr.stack is not None else None
    )
    # Per-reviewer status, preserving the viewer's configured order, so the
    # card can render one chip per tracked reviewer. The aggregate
    # ``approved`` / ``review_requested`` booleans stay for the column
    # bucketing and any consumer that only cares "did anyone act?".
    reviewer_status = [
        {
            "login": login,
            "approved": pr.is_approved_by(login),
            "review_requested": pr.is_review_requested_from(login),
        }
        for login in reviewers
    ]
    return {
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "repo": pr.repo,
        "author": pr.author,
        "is_draft": pr.is_draft,
        "is_ready": pr.is_ready,
        "checks": _serialize_checks(pr.checks),
        "comments_human": pr.comments_human,
        "comments_bot": pr.comments_bot,
        "preview_url": pr.preview_url,
        "conflicts": pr.conflicts,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "linear_url": pr.linear_url,
        "video_url": pr.video_url,
        "updated_at": pr.updated_at,
        "column": pr.column_for(reviewers),
        "approved": any(s["approved"] for s in reviewer_status),
        "review_requested": any(s["review_requested"] for s in reviewer_status),
        "reviewers": reviewer_status,
        "stack_id": stack_id,
        "stack_order": pr.stack_order,
        "stack_depth": pr.stack_depth,
        "stack_co_column": pr.stack_co_column,
        "stack_nodes": _serialize_stack_nodes(pr, reviewers),
    }


def serialize_review(
    pr: ReviewPR, reviewers: list[str] | None = None
) -> dict[str, object]:
    stack_id = (
        f"{pr.repo}#{pr.stack.nodes[0].number}" if pr.stack is not None else None
    )
    return {
        "number": pr.number,
        "title": pr.title,
        "url": pr.url,
        "repo": pr.repo,
        "author": pr.author,
        "is_draft": pr.is_draft,
        "checks": _serialize_checks(pr.checks),
        "conflicts": pr.conflicts,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "updated_at": pr.updated_at,
        "requested_at": pr.requested_at,
        "stack_id": stack_id,
        "stack_order": pr.stack_order,
        "stack_depth": pr.stack_depth,
        "stack_co_column": pr.stack_co_column,
        "stack_nodes": _serialize_stack_nodes(pr, reviewers or []),
    }


def _serialize_repos(
    prs: list[PR], reviews: list[ReviewPR]
) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for pr in prs:
        counts[pr.repo] = counts.get(pr.repo, 0) + 1
    for pr in reviews:
        counts[pr.repo] = counts.get(pr.repo, 0) + 1
    return [
        {"repo": repo, "count": count}
        for repo, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _iso_z(when: datetime) -> str:
    return when.isoformat().replace("+00:00", "Z")


def serialize_dashboard(
    *,
    prs: list[PR],
    reviews: list[ReviewPR],
    reviewers_param: str | None,
    last_polled_at: datetime | None,
    error_message: str,
    error_reset_at: datetime | None,
    poll_interval_seconds: int,
) -> dict[str, object]:
    """Build the full ``/api/dashboard`` payload for one viewer.

    Stack attachment happens here (not in the poller) because the
    co-column layout decision depends on the viewer's tracked reviewers.
    Review PRs get the same structural pass so the Reviewing tab can
    group stacked requests.
    """
    reviewers = effective_reviewers(reviewers_param)
    stacked = attach_stacks(prs, reviewers)
    stacked_reviews = attach_stacks(reviews, reviewers)
    error = None
    if error_message:
        error = {
            "message": error_message,
            "reset_at": _iso_z(error_reset_at) if error_reset_at else None,
        }
    return {
        "prs": [serialize_pr(pr, reviewers) for pr in stacked],
        "reviews": [serialize_review(pr, reviewers) for pr in stacked_reviews],
        "repos": _serialize_repos(prs, reviews),
        "reviewers": reviewers,
        "last_polled_at": _iso_z(last_polled_at) if last_polled_at else None,
        "error": error,
        "poll_interval_seconds": poll_interval_seconds,
    }
