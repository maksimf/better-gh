"""Domain models for PRs and their derived rendering state."""
from __future__ import annotations

from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field


def normalize_reviewers(reviewers: str | Iterable[str] | None) -> set[str]:
    """Coerce a reviewer spec into a set of lower-cased, non-empty logins.

    Accepts the historical single-login string (so existing single-reviewer
    call sites keep working unchanged), an iterable of logins (the
    multi-reviewer case), or ``None``. A blank/whitespace login is dropped
    so ``""`` cleanly means "track nobody".
    """
    if reviewers is None:
        return set()
    if isinstance(reviewers, str):
        rl = reviewers.strip().lower()
        return {rl} if rl else set()
    out: set[str] = set()
    for r in reviewers:
        rl = (r or "").strip().lower()
        if rl:
            out.add(rl)
    return out


class FailedCheck(BaseModel):
    """One failing CI check, surfaced so the UI can list it by name.

    ``url`` is GitHub's per-check details page (CheckRun.detailsUrl or
    StatusContext.targetUrl); ``None`` when the upstream payload didn't
    include one (rare, but e.g. some external status reporters omit it).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    url: str | None = None


class Checks(BaseModel):
    """Bucketed CI check counts for a single PR.

    ``failed_names`` carries one entry per failing check so the
    frontend can pop up the actual names when the failed cell is
    clicked, instead of just showing the bare count.
    """

    model_config = ConfigDict(frozen=True)

    passed: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    failed_names: tuple[FailedCheck, ...] = ()


Column = Literal["approved", "ready", "progress"]


def _column_for(
    *,
    is_ready: bool,
    approver_logins: tuple[str, ...],
    reviewers: str | Iterable[str] | None,
) -> Column:
    """Compute which Trello column a PR belongs in for a given viewer.

    Lives at module scope (not on the model) so both :class:`PR` and
    :class:`StackNode` can share the same definition without duplicating
    the rule -- and so the rule shows up exactly once in tests.

    ``reviewers`` may be a single login (the legacy single-reviewer case)
    or an iterable of logins (multi-reviewer tracking). A PR lands in
    ``approved`` when *any* tracked reviewer has approved it.
    """
    tracked = normalize_reviewers(reviewers)
    if tracked:
        for approver in approver_logins:
            if approver.lower() in tracked:
                return "approved"
    return "ready" if is_ready else "progress"


class StackNode(BaseModel):
    """One PR's position inside a detected stack.

    Stacks are forests rooted at PRs whose base branch isn't another
    dashboard PR's head. ``depth`` is 0 for the root and increments by
    one per generation; ``parent_number`` is ``None`` only for the root.

    ``approver_logins`` + ``is_ready`` carry just enough of the source
    PR's state to recompute the per-viewer column for the badge shown
    next to each non-self node in the inline stack tree.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    url: str
    repo: str
    depth: int = Field(ge=0)
    parent_number: int | None
    is_ready: bool = False
    approver_logins: tuple[str, ...] = ()

    def column_for(self, reviewers: str | Iterable[str] | None) -> Column:
        return _column_for(
            is_ready=self.is_ready,
            approver_logins=self.approver_logins,
            reviewers=reviewers,
        )


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
    """A pull request as displayed on the dashboard.

    Reviewer-dependent UI (the per-card R chip / "Request review"
    button, and the APPROVED column placement) is computed from raw
    reviewer state at *render* time via :meth:`is_approved_by`,
    :meth:`is_review_requested_from`, and :meth:`column_for`. The model
    itself stays reviewer-agnostic so one cached snapshot can serve
    every viewer regardless of which login they've configured to
    track.
    """

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
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    updated_at: str
    # Raw reviewer state from GitHub. ``requested_reviewers`` is the
    # current "Reviewers" list on the PR (non-team users only).
    # ``approver_logins`` is the set of users whose most recent review
    # is APPROVED -- a viewer-agnostic source of truth that
    # :meth:`is_approved_by` filters down to whichever login the
    # current viewer is tracking.
    requested_reviewers: tuple[str, ...] = ()
    approver_logins: tuple[str, ...] = ()
    linear_url: str | None = None
    video_url: str | None = None
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
    # collapse the cards into a single indented group instead. Like the
    # column itself, ``stack_co_column`` is reviewer-dependent (an
    # approval can split a previously co-column stack), so these get
    # re-populated per render by ``attach_stacks``.
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
            and self.conflicts == 0
        )

    def is_approved_by(self, reviewer: str | None) -> bool:
        """Has ``reviewer``'s most recent review been APPROVED?"""
        rl = (reviewer or "").lower().strip()
        if not rl:
            return False
        return any(a.lower() == rl for a in self.approver_logins)

    def is_review_requested_from(self, reviewer: str | None) -> bool:
        """Is ``reviewer`` currently on the requested-reviewers list?"""
        rl = (reviewer or "").lower().strip()
        if not rl:
            return False
        return any(r.lower() == rl for r in self.requested_reviewers)

    def column_for(self, reviewers: str | Iterable[str] | None) -> Column:
        return _column_for(
            is_ready=self.is_ready,
            approver_logins=self.approver_logins,
            reviewers=reviewers,
        )

    def fingerprint(self) -> tuple:
        """Stable hashable tuple of every field that affects rendering.

        The poller uses this to detect "did anything visible change?"
        without diffing rendered HTML. We hash the raw reviewer state
        (not any per-viewer derived booleans) so a snapshot can be
        shared across viewers without spurious diffs when only the
        configured reviewer differs.
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
            self.checks.failed_names,
            self.comments_human,
            self.comments_bot,
            self.preview_url,
            self.conflicts,
            self.additions,
            self.deletions,
            self.requested_reviewers,
            self.approver_logins,
            self.linear_url,
            self.video_url,
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
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
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
            self.checks.failed_names,
            self.conflicts,
            self.additions,
            self.deletions,
            self.requested_at,
        )
