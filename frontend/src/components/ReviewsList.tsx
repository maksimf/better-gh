import type { ReviewPr } from "../api/types";
import { useNow } from "../hooks/useRelativeTime";
import { DeferredSection } from "./DeferredSection";
import { ReviewRow } from "./ReviewRow";

function AllClear() {
  return (
    <section className="empty-state empty-state--reviews" aria-live="polite">
      <div className="empty-state-mark" aria-hidden="true">
        <span className="shape shape--circle"></span>
        <span className="shape shape--square"></span>
        <span className="shape shape--triangle"></span>
      </div>
      <h2 className="empty-state-title">ALL CLEAR</h2>
      <p className="empty-state-sub">No PRs are waiting for your review.</p>
    </section>
  );
}

export function ReviewsList({
  reviews,
  deferredReviews,
  reviewedHas,
  onToggleReviewed,
  deferredHas,
  onToggleDeferred,
}: {
  reviews: ReviewPr[];
  deferredReviews: ReviewPr[];
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  deferredHas: (key: string) => boolean;
  onToggleDeferred: (key: string) => void;
}) {
  const now = useNow();

  if (reviews.length === 0 && deferredReviews.length === 0) return <AllClear />;

  const rowProps = {
    now,
    reviewedHas,
    onToggleReviewed,
    deferredHas,
    onToggleDeferred,
  };

  function renderRow(pr: ReviewPr) {
    return (
      <ReviewRow
        key={`${pr.repo}#${pr.number}`}
        pr={pr}
        {...rowProps}
      />
    );
  }

  return (
    <>
      {reviews.length > 0 && (
        <div className="reviews-list" aria-live="polite">
          {reviews.map((pr) => renderRow(pr))}
        </div>
      )}
      {deferredReviews.length > 0 && (
        <div className="reviews-list reviews-list--deferred-only">
          <DeferredSection count={deferredReviews.length}>
            {deferredReviews.map((pr) => renderRow(pr))}
          </DeferredSection>
        </div>
      )}
    </>
  );
}
