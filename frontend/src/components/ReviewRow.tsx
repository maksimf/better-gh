import type { ReviewPr } from "../api/types";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { formatRelative } from "../hooks/useRelativeTime";
import { ChecksPill, Conflicts } from "./ChecksPill";
import { PrLocStats } from "./PrLocStats";
import { ReviewedToggle } from "./ReviewedToggle";

export function ReviewRow({
  pr,
  now,
  reviewedHas,
  onToggleReviewed,
}: {
  pr: ReviewPr;
  now: number;
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
}) {
  const key = reviewedKey(pr.repo, pr.number);
  const isReviewed = reviewedHas(key);
  const classes = [
    "review-row",
    pr.is_draft && "is-draft",
    isReviewed && "is-manually-reviewed",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={classes} data-repo={pr.repo}>
      <div className="review-main">
        <a className="review-number" href={pr.url} target="_blank" rel="noopener">
          #{pr.number}
        </a>
        <h3 className="review-title">
          <a href={pr.url} target="_blank" rel="noopener">
            {pr.title}
          </a>
          <PrLocStats additions={pr.additions} deletions={pr.deletions} />
        </h3>
        <span className="review-repo">{pr.repo}</span>
        <span className="review-author">@{pr.author}</span>
        {pr.is_draft && <span className="pr-tag pr-tag--draft">Draft</span>}
        {pr.requested_at && (
          <span
            className="review-requested-at"
            title={`Review requested at ${pr.requested_at}`}
          >
            requested{" "}
            <span className="review-requested-relative">
              {formatRelative(pr.requested_at, now)}
            </span>
          </span>
        )}
      </div>
      <div className="review-meta">
        <ChecksPill checks={pr.checks} />
        <Conflicts conflicts={pr.conflicts} />
        <ReviewedToggle
          pressed={isReviewed}
          onToggle={() => onToggleReviewed(key)}
        />
      </div>
    </article>
  );
}
