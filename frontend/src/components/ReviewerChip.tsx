import { useState } from "react";

import { useRequestReview } from "../api/queries";
import { CheckIcon } from "./icons";

/**
 * The per-card "R" affordance. Three states, mirroring the old template:
 *   - approved by the tracked reviewer  -> green double-check chip
 *   - review already requested           -> blue single-check chip
 *   - neither                            -> "Request review" button
 * Hidden entirely when no reviewer is configured (reviewer === "").
 */
export function ReviewerChip({
  reviewer,
  approved,
  reviewRequested,
  owner,
  repo,
  number,
}: {
  reviewer: string;
  approved: boolean;
  reviewRequested: boolean;
  owner: string;
  repo: string;
  number: number;
}) {
  const requestReview = useRequestReview();
  const [optimisticRequested, setOptimisticRequested] = useState(false);
  const [error, setError] = useState(false);

  if (!reviewer) return null;

  if (approved) {
    return (
      <span className="chip chip--approved" title={`Approved by @${reviewer}`}>
        <span className="chip-key">R</span>
        <span className="chip-checks" aria-hidden="true">
          <CheckIcon />
          <CheckIcon />
        </span>
      </span>
    );
  }

  if (reviewRequested || optimisticRequested) {
    return (
      <span
        className="chip chip--review"
        title={`Review requested from @${reviewer}`}
      >
        <span className="chip-key">R</span>
        <span className="chip-checks" aria-hidden="true">
          <CheckIcon />
        </span>
      </span>
    );
  }

  function onClick() {
    setError(false);
    requestReview.mutate(
      { ref: { owner, repo, number }, reviewer },
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
      className={`review-request${error ? " is-error" : ""}`}
      title={
        error ? "Couldn't request review." : `Request review from @${reviewer}`
      }
      aria-label={`Request review from @${reviewer}`}
      disabled={requestReview.isPending}
      onClick={onClick}
    >
      Request review
    </button>
  );
}
