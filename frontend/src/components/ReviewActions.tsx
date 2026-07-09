import { useState } from "react";

import { useSubmitReview } from "../api/queries";
import type { ReviewEvent } from "../api/types";
import { CheckIcon } from "./icons";

type Submitted = ReviewEvent | null;

export function ReviewActions({
  owner,
  repo,
  number,
  isOwnPr,
}: {
  owner: string;
  repo: string;
  number: number;
  isOwnPr: boolean;
}) {
  const submit = useSubmitReview();
  const [summary, setSummary] = useState("");
  const [submitted, setSubmitted] = useState<Submitted>(null);
  const [error, setError] = useState<string | null>(null);

  function showError(message: string) {
    setError(message);
    window.setTimeout(() => setError(null), 4000);
  }

  function doSubmit(event: ReviewEvent) {
    setError(null);
    submit.mutate(
      { ref: { owner, repo, number }, event, body: summary },
      {
        onSuccess: () => {
          setSubmitted(event);
          setSummary("");
        },
        onError: (e) => showError(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  if (submitted) {
    const label =
      submitted === "APPROVE"
        ? "APPROVED"
        : submitted === "REQUEST_CHANGES"
          ? "CHANGES REQUESTED"
          : "COMMENTED";
    return (
      <div className="review-actions">
        <span
          className={`review-actions-done review-actions-done--${submitted.toLowerCase()}`}
          aria-disabled="true"
        >
          {label}{" "}
          {submitted === "APPROVE" && (
            <span aria-hidden="true">
              <CheckIcon />
            </span>
          )}
        </span>
      </div>
    );
  }

  return (
    <div className="review-actions">
      <textarea
        className="review-actions-summary"
        placeholder="Review summary (optional)"
        rows={2}
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        disabled={submit.isPending}
      />
      <div className="review-actions-buttons">
        {!isOwnPr && (
          <>
            <button
              type="button"
              className={`approve-button${error ? " is-error" : ""}`}
              title={error ?? "Approve this PR"}
              disabled={submit.isPending}
              onClick={() => doSubmit("APPROVE")}
            >
              {submit.isPending ? "…" : "APPROVE"}
              {!submit.isPending && !error && (
                <span aria-hidden="true">
                  <CheckIcon />
                </span>
              )}
            </button>
            <button
              type="button"
              className="review-button review-button--changes"
              title={error ?? "Request changes (summary required)"}
              disabled={submit.isPending || !summary.trim()}
              onClick={() => doSubmit("REQUEST_CHANGES")}
            >
              REQUEST CHANGES
            </button>
          </>
        )}
        <button
          type="button"
          className="review-button review-button--comment"
          title={error ?? "Leave a review comment (summary required)"}
          disabled={submit.isPending || !summary.trim()}
          onClick={() => doSubmit("COMMENT")}
        >
          COMMENT
        </button>
      </div>
      {error && <p className="review-actions-error">{error}</p>}
    </div>
  );
}
