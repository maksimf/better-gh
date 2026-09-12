import type { CSSProperties } from "react";

import type { ReviewPr } from "../api/types";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { formatRelative } from "../hooks/useRelativeTime";
import { Button } from "../ui/Button";
import { Tag } from "../ui/Tag";
import { ApproveButton } from "./ApproveButton";
import { ChecksPill, Conflicts } from "./ChecksPill";
import { DeferredToggle } from "./DeferredToggle";
import { PrLocStats } from "./PrLocStats";
import { ReviewedToggle } from "./ReviewedToggle";

function splitRepo(repo: string): { owner: string; name: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, name: "" };
  return { owner: repo.slice(0, slash), name: repo.slice(slash + 1) };
}

export function ReviewRow({
  pr,
  now,
  reviewedHas,
  onToggleReviewed,
  deferredHas,
  onToggleDeferred,
  selected = false,
  onSelect,
  inStackGroup = false,
}: {
  pr: ReviewPr;
  now: number;
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  deferredHas: (key: string) => boolean;
  onToggleDeferred: (key: string) => void;
  selected?: boolean;
  onSelect?: () => void;
  inStackGroup?: boolean;
}) {
  const key = reviewedKey(pr.repo, pr.number);
  const isReviewed = reviewedHas(key);
  const isDeferred = deferredHas(key);
  const { owner, name } = splitRepo(pr.repo);
  const grouped = inStackGroup || pr.stack_co_column;
  const classes = [
    "review-row",
    pr.is_draft && "is-draft",
    pr.stack_id && "is-stacked",
    grouped && "is-stack-co-column",
    inStackGroup && "is-stack-grouped",
    isReviewed && "is-manually-reviewed",
    selected && "is-selected",
  ]
    .filter(Boolean)
    .join(" ");
  const style: CSSProperties | undefined = grouped
    ? ({ "--stack-depth": pr.stack_depth ?? 0 } as CSSProperties)
    : undefined;

  // Select the row to open the diff, but let real links/buttons inside
  // the row do their own thing (open GitHub, toggle markers, approve).
  function handleRowClick(e: React.MouseEvent<HTMLElement>) {
    if (!onSelect) return;
    if ((e.target as HTMLElement).closest("a, button")) return;
    onSelect();
  }

  return (
    <article
      className={classes}
      data-repo={pr.repo}
      aria-current={selected || undefined}
      style={style}
      onClick={handleRowClick}
    >
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
        {pr.is_draft && <Tag variant="draft">Draft</Tag>}
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
        {onSelect && (
          <Button
            surface="toggle"
            variant="diff"
            active={selected}
            title={selected ? "Hide diff" : "Review diff"}
            onClick={onSelect}
          >
            {selected ? "VIEWING" : "REVIEW"}
          </Button>
        )}
        <ApproveButton owner={owner} repo={name} number={pr.number} />
        <ChecksPill checks={pr.checks} />
        <Conflicts conflicts={pr.conflicts} />
        <ReviewedToggle
          pressed={isReviewed}
          onToggle={() => onToggleReviewed(key)}
        />
        <DeferredToggle pressed={isDeferred} onToggle={() => onToggleDeferred(key)} />
      </div>
    </article>
  );
}
