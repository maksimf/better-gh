import { useState } from "react";

import { useSubmitReview } from "../api/queries";
import type { ReviewEvent } from "../api/types";
import { ActionButton } from "../ui/ActionButton";
import { Button } from "../ui/Button";
import { useTransientError } from "../ui/useTransientError";
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
  const { error, showError, clearError } = useTransientError();

  function doSubmit(event: ReviewEvent) {
    clearError();
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
            <ActionButton
              kind="approve"
              error={Boolean(error)}
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
            </ActionButton>
            <Button
              surface="review"
              variant="changes"
              title={error ?? "Request changes (summary required)"}
              disabled={submit.isPending || !summary.trim()}
              onClick={() => doSubmit("REQUEST_CHANGES")}
            >
              REQUEST CHANGES
            </Button>
          </>
        )}
        <Button
          surface="review"
          variant="comment"
          title={error ?? "Leave a review comment (summary required)"}
          disabled={submit.isPending || !summary.trim()}
          onClick={() => doSubmit("COMMENT")}
        >
          COMMENT
        </Button>
      </div>
      {error && <p className="review-actions-error">{error}</p>}
    </div>
  );
}
