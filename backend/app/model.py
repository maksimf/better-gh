"""Domain models for PRs and their derived rendering state."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Checks(BaseModel):
    """Bucketed CI check counts for a single PR."""

    model_config = ConfigDict(frozen=True)

    passed: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class PR(BaseModel):
    """A pull request as displayed on the dashboard."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    repo: str
    author: str
    is_draft: bool
    checks: Checks
    comments_human: int = Field(ge=0)
    comments_bot: int = Field(ge=0)
    preview_url: str | None
    conflicts: int = Field(ge=0)
    updated_at: str
    review_requested: bool = False
    approved_by_reviewer: bool = False
    linear_url: str | None = None

    @property
    def is_ready(self) -> bool:
        """Implements the readiness rule from the spec."""
        return (
            not self.is_draft
            and self.checks.failed == 0
            and self.checks.pending == 0
            and self.comments_human == 0
            and self.comments_bot == 0
            and self.preview_url is not None
            and self.conflicts == 0
        )

    @property
    def column(self) -> Literal["approved", "ready", "progress"]:
        if self.approved_by_reviewer:
            return "approved"
        return "ready" if self.is_ready else "progress"

    def fingerprint(self) -> tuple:
        """Stable hashable tuple of every field that affects rendering.

        The poller uses this to detect "did anything visible change?"
        without diffing rendered HTML.
        """
        return (
            self.number,
            self.title,
            self.url,
            self.repo,
            self.author,
            self.is_draft,
            self.checks.passed,
            self.checks.pending,
            self.checks.failed,
            self.comments_human,
            self.comments_bot,
            self.preview_url,
            self.conflicts,
            self.review_requested,
            self.approved_by_reviewer,
            self.linear_url,
        )


class ReviewPR(BaseModel):
    """A PR where the viewer has been requested as a reviewer.

    Slim sibling of ``PR`` -- the "Reviewing" tab only needs enough to
    show a clickable title, a checks pill, a conflicts badge, and "when
    was the review requested" hint, so we deliberately don't carry
    comments / preview / approval state here.

    ``requested_at`` is the ISO-8601 timestamp of the most recent
    ReviewRequestedEvent that targets the viewer; empty when GitHub's
    timeline doesn't surface one (e.g. the request is older than the
    timeline window we fetched).
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    repo: str
    author: str
    is_draft: bool
    checks: Checks
    conflicts: int = Field(ge=0)
    updated_at: str
    requested_at: str = ""

    def fingerprint(self) -> tuple:
        return (
            self.number,
            self.title,
            self.url,
            self.repo,
            self.author,
            self.is_draft,
            self.checks.passed,
            self.checks.pending,
            self.checks.failed,
            self.conflicts,
            self.requested_at,
        )
