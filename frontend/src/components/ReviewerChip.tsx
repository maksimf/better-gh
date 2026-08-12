import { useState } from "react";

import { useAddPrComment, useRequestReview } from "../api/queries";
import type { ReviewerStatus } from "../api/types";
import { ActionButton } from "../ui/ActionButton";
import { Chip } from "../ui/Chip";
import { useTransientFlag } from "../ui/useTransientFlag";
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
  const { isError, show, clear } = useTransientFlag();

  if (approved) {
    return (
      <Chip
        variant="approved"
        initial={initial(login)}
        title={`Approved by @${login}`}
        checks={
          <>
            <CheckIcon />
            <CheckIcon />
          </>
        }
      />
    );
  }

  if (review_requested || optimisticRequested) {
    return (
      <Chip
        variant="review"
        initial={initial(login)}
        title={`Review requested from @${login}`}
        checks={<CheckIcon />}
      />
    );
  }

  function onClick() {
    clear();
    requestReview.mutate(
      { ref: { owner, repo, number }, reviewers: [login] },
      {
        onSuccess: () => setOptimisticRequested(true),
        onError: () => show(),
      },
    );
  }

  return (
    <Chip
      variant="pending"
      initial={initial(login)}
      error={isError}
      title={
        isError
          ? `Couldn't request review from @${login}.`
          : `Request review from @${login}`
      }
      ariaLabel={`Request review from @${login}`}
      disabled={requestReview.isPending}
      onClick={onClick}
    />
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
  const { isError, show, clear } = useTransientFlag();

  const pending = reviewers.filter(
    (r) => !r.approved && !r.review_requested,
  );
  if (pending.length === 0 || done) return null;

  const logins = pending.map((r) => r.login);
  const label = pending.length === 1 ? "Request review" : "Request reviews";

  function onClick() {
    clear();
    requestReview.mutate(
      { ref: { owner, repo, number }, reviewers: logins },
      {
        onSuccess: () => setDone(true),
        onError: () => show(),
      },
    );
  }

  return (
    <ActionButton
      kind="review-request"
      error={isError}
      title={
        isError
          ? "Couldn't request review."
          : `Request review from ${logins.map((l) => `@${l}`).join(", ")}`
      }
      aria-label={`${label} from ${logins.map((l) => `@${l}`).join(", ")}`}
      disabled={requestReview.isPending}
      onClick={onClick}
    >
      {label}
    </ActionButton>
  );
}

/**
 * The primary action for a PR assigned to the viewer but authored by
 * somebody else. Mentions every tracked reviewer in a conversation comment
 * instead of trying to change the PR's requested-reviewers list.
 */
export function NotifyReviewerAction({
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
  const addComment = useAddPrComment();
  const [done, setDone] = useState(false);
  const { isError, show, clear } = useTransientFlag();
  const logins = reviewers.map((reviewer) => reviewer.login);

  if (logins.length === 0 || done) return null;

  function onClick() {
    clear();
    addComment.mutate(
      {
        ref: { owner, repo, number },
        body: `${logins.map((login) => `@${login}`).join(" ")} this PR is now ready to be reviewed`,
      },
      {
        onSuccess: () => setDone(true),
        onError: () => show(),
      },
    );
  }

  const mentions = logins.map((login) => `@${login}`).join(", ");
  return (
    <ActionButton
      kind="review-request"
      error={isError}
      title={
        isError
          ? "Couldn't notify reviewers."
          : `Notify ${mentions} that this PR is ready for review`
      }
      aria-label={`Notify reviewers ${mentions}`}
      disabled={addComment.isPending}
      onClick={onClick}
    >
      Notify reviewer
    </ActionButton>
  );
}
