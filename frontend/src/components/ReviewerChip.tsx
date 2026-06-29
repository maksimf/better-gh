import { useState } from "react";

import { useRequestReview } from "../api/queries";
import type { ReviewerStatus } from "../api/types";
import { CheckIcon } from "./icons";

function initial(login: string): string {
  return (login.trim()[0] ?? "?").toUpperCase();
}

/**
 * The per-card reviewer status strip: one chip per tracked reviewer.
 *   - approved            -> green double-check chip
 *   - review requested    -> blue single-check chip
 *   - neither             -> a yellow "request this reviewer" button chip
 * Renders nothing when no reviewers are tracked (reviewers === []).
 */
export function ReviewerChips({
  reviewers,
  owner,
  repo,
  number,
}: {
  reviewers: ReviewerStatus[];
  owner: string;
  repo: string;
  number: number;
}) {
  if (reviewers.length === 0) return null;
  return (
    <span className="reviewer-chips">
      {reviewers.map((r) => (
        <ReviewerChip
          key={r.login}
          status={r}
          owner={owner}
          repo={repo}
          number={number}
        />
      ))}
    </span>
  );
}

function ReviewerChip({
  status,
  owner,
  repo,
  number,
}: {
  status: ReviewerStatus;
  owner: string;
  repo: string;
  number: number;
}) {
  const { login, approved, review_requested } = status;
  const requestReview = useRequestReview();
  const [optimisticRequested, setOptimisticRequested] = useState(false);
  const [error, setError] = useState(false);

  if (approved) {
    return (
      <span
        className="chip chip--approved reviewer-chip"
        title={`Approved by @${login}`}
      >
        <span className="chip-key">{initial(login)}</span>
        <span className="chip-checks" aria-hidden="true">
          <CheckIcon />
          <CheckIcon />
        </span>
      </span>
    );
  }

  if (review_requested || optimisticRequested) {
    return (
      <span
        className="chip chip--review reviewer-chip"
        title={`Review requested from @${login}`}
      >
        <span className="chip-key">{initial(login)}</span>
        <span className="chip-checks" aria-hidden="true">
          <CheckIcon />
        </span>
      </span>
    );
  }

  function onClick() {
    setError(false);
    requestReview.mutate(
      { ref: { owner, repo, number }, reviewers: [login] },
      {
        onSuccess: () => setOptimisticRequested(true),
        onError: () => {
          setError(true);
          window.setTimeout(() => setError(false), 2400);
        },
      },
    );
  }

  return (
    <button
      type="button"
      className={`chip reviewer-chip reviewer-chip--pending${
        error ? " is-error" : ""
      }`}
      title={
        error
          ? `Couldn't request review from @${login}.`
          : `Request review from @${login}`
      }
      aria-label={`Request review from @${login}`}
      disabled={requestReview.isPending}
      onClick={onClick}
    >
      <span className="chip-key">{initial(login)}</span>
    </button>
  );
}

/**
 * The card's primary call-to-action: request a review from every tracked
 * reviewer who hasn't already approved or been asked. Renders nothing when
 * there's nobody left to request (or no reviewers are tracked).
 */
export function RequestReviewAction({
  reviewers,
  owner,
  repo,
  number,
}: {
  reviewers: ReviewerStatus[];
  owner: string;
  repo: string;
  number: number;
}) {
  const requestReview = useRequestReview();
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);

  const pending = reviewers.filter(
    (r) => !r.approved && !r.review_requested,
  );
  if (pending.length === 0 || done) return null;

  const logins = pending.map((r) => r.login);
  const label = pending.length === 1 ? "Request review" : "Request reviews";

  function onClick() {
    setError(false);
    requestReview.mutate(
      { ref: { owner, repo, number }, reviewers: logins },
      {
        onSuccess: () => setDone(true),
        onError: () => {
          setError(true);
          window.setTimeout(() => setError(false), 2400);
        },
      },
    );
  }

  return (
    <button
      type="button"
      className={`review-request${error ? " is-error" : ""}`}
      title={
        error
          ? "Couldn't request review."
          : `Request review from ${logins.map((l) => `@${l}`).join(", ")}`
      }
      aria-label={`${label} from ${logins.map((l) => `@${l}`).join(", ")}`}
      disabled={requestReview.isPending}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
