import type { ReviewPr } from "../api/types";
import { useNow } from "../hooks/useRelativeTime";
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
  reviewedHas,
  onToggleReviewed,
}: {
  reviews: ReviewPr[];
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
}) {
  const now = useNow();

  if (reviews.length === 0) return <AllClear />;

  return (
    <div className="reviews-list" aria-live="polite">
      {reviews.map((pr) => (
        <ReviewRow
          key={`${pr.repo}#${pr.number}`}
          pr={pr}
          now={now}
          reviewedHas={reviewedHas}
          onToggleReviewed={onToggleReviewed}
        />
      ))}
    </div>
  );
}
