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


def effective_reviewer(reviewer_login: str | None) -> str:
    """Pick the reviewer login a serialization should use.

    Three-tier fallback so the per-viewer override layers cleanly on
    top of the deploy-wide default:

    * ``None`` -> use ``settings.REVIEWER_LOGIN`` (the "I haven't
      configured anything; show the default reviewer" case).
    * Empty string -> empty (the explicit "no reviewer tracking, hide
      the chip" case -- distinct from "unset").
    * Anything else -> the trimmed, lower-cased login.
    """
    if reviewer_login is None:
        return (settings.REVIEWER_LOGIN or "").strip().lower()
    return reviewer_login.strip().lower()


def _serialize_checks(pr_checks) -> dict[str, object]:
    return {
        "passed": pr_checks.passed,
        "pending": pr_checks.pending,
        "failed": pr_checks.failed,
        "failed_names": [
            {"name": c.name, "url": c.url} for c in pr_checks.failed_names
        ],
    }


def _serialize_stack_nodes(pr: PR, reviewer: str) -> list[dict[str, object]]:
    if pr.stack is None:
        return []
    return [
        {
            "number": node.number,
            "title": node.title,
            "url": node.url,
            "depth": node.depth,
            "column": node.column_for(reviewer),
            "is_self": node.number == pr.number,
        }
        for node in pr.stack.nodes
    ]


def serialize_pr(pr: PR, reviewer: str) -> dict[str, object]:
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
        "is_ready": pr.is_ready,
        "checks": _serialize_checks(pr.checks),
        "comments_human": pr.comments_human,
        "comments_bot": pr.comments_bot,
        "preview_url": pr.preview_url,
        "conflicts": pr.conflicts,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "linear_url": pr.linear_url,
        "updated_at": pr.updated_at,
        "column": pr.column_for(reviewer),
        "approved": pr.is_approved_by(reviewer),
        "review_requested": pr.is_review_requested_from(reviewer),
        "stack_id": stack_id,
        "stack_order": pr.stack_order,
        "stack_depth": pr.stack_depth,
        "stack_co_column": pr.stack_co_column,
        "stack_nodes": _serialize_stack_nodes(pr, reviewer),
    }


def serialize_review(pr: ReviewPR) -> dict[str, object]:
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
    reviewer_login: str | None,
    last_polled_at: datetime | None,
    error_message: str,
    error_reset_at: datetime | None,
    poll_interval_seconds: int,
) -> dict[str, object]:
    """Build the full ``/api/dashboard`` payload for one viewer.

    Stack attachment happens here (not in the poller) because the
    co-column layout decision depends on the viewer's tracked reviewer.
    """
    reviewer = effective_reviewer(reviewer_login)
    stacked = attach_stacks(prs, reviewer)
    error = None
    if error_message:
        error = {
            "message": error_message,
            "reset_at": _iso_z(error_reset_at) if error_reset_at else None,
        }
    return {
        "prs": [serialize_pr(pr, reviewer) for pr in stacked],
        "reviews": [serialize_review(pr) for pr in reviews],
        "repos": _serialize_repos(prs, reviews),
        "reviewer": reviewer,
        "last_polled_at": _iso_z(last_polled_at) if last_polled_at else None,
        "error": error,
        "poll_interval_seconds": poll_interval_seconds,
    }
