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


class StackNode(BaseModel):
    """One PR's position inside a detected stack.

    Stacks are forests rooted at PRs whose base branch isn't another
    dashboard PR's head. ``depth`` is 0 for the root and increments by
    one per generation; ``parent_number`` is ``None`` only for the root.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    repo: str
    depth: int = Field(ge=0)
    parent_number: int | None
    column: Literal["approved", "ready", "progress"]


class Stack(BaseModel):
    """A connected chain of 2+ PRs where each non-root merges into a parent.

    ``nodes`` is in pre-order traversal: the root comes first, then each
    subtree in turn. Every PR that belongs to the stack carries the same
    ``Stack`` instance on ``PR.stack`` so the template can render the
    same tree from any card's perspective.
    """

    model_config = ConfigDict(frozen=True)

    nodes: tuple[StackNode, ...]


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
    base_ref: str = ""
    head_ref: str = ""
    stack: Stack | None = None
    # Derived stack-layout fields populated by ``app.stack.attach_stacks``.
    # ``stack_depth`` mirrors ``StackNode.depth`` for this PR's node;
    # ``stack_order`` is its position (0-based) inside ``stack.nodes`` so
    # the frontend can re-sort co-column cards into pre-order even when
    # the parent list came in by ``updated_at``. ``stack_co_column`` is
    # ``True`` iff every node in the stack lands in the same column as
    # this PR -- the frontend uses that to hide the inline tree and
    # collapse the cards into a single indented group instead.
    stack_depth: int | None = None
    stack_order: int | None = None
    stack_co_column: bool = False

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
            self.base_ref,
            self.head_ref,
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
