import type { CSSProperties } from "react";

import type { Pr } from "../api/types";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { ChecksPill, Conflicts } from "./ChecksPill";
import { CloudAgentLink } from "./CloudAgentLink";
import { CommentsPill } from "./CommentsPill";
import { DraftButton } from "./DraftButton";
import { MergeButton } from "./MergeButton";
import { NoteButton } from "./NoteButton";
import { PrStack } from "./PrStack";
import { PreviewLink } from "./PreviewLink";
import { ReviewedToggle } from "./ReviewedToggle";
import { ReviewerChip } from "./ReviewerChip";
import { WatchToggle } from "./WatchToggle";

function splitRepo(repo: string): { owner: string; name: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, name: "" };
  return { owner: repo.slice(0, slash), name: repo.slice(slash + 1) };
}

export function PrCard({
  pr,
  reviewer,
  reviewedHas,
  onToggleReviewed,
  watchedHas,
  onToggleWatch,
  watchDisabled,
}: {
  pr: Pr;
  reviewer: string;
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  watchedHas: (key: string) => boolean;
  onToggleWatch: (key: string) => void;
  watchDisabled: boolean;
}) {
  const { owner, name } = splitRepo(pr.repo);
  const key = reviewedKey(pr.repo, pr.number);
  const isReviewed = reviewedHas(key);
  const isWatched = watchedHas(key);
  const showInlineStack = pr.stack_nodes.length > 0 && !pr.stack_co_column;

  const classes = [
    "pr-card",
    pr.is_ready && "is-ready",
    pr.is_draft && "is-draft",
    pr.stack_id && "is-stacked",
    pr.stack_co_column && "is-stack-co-column",
    isReviewed && "is-manually-reviewed",
  ]
    .filter(Boolean)
    .join(" ");

  const style: CSSProperties | undefined = pr.stack_co_column
    ? ({ "--stack-depth": pr.stack_depth ?? 0 } as CSSProperties)
    : undefined;

  return (
    <article className={classes} data-repo={pr.repo} data-column={pr.column} style={style}>
      <header className="pr-head">
        <a className="pr-number" href={pr.url} target="_blank" rel="noopener">
          #{pr.number}
        </a>
        <h3 className="pr-title">
          <a href={pr.url} target="_blank" rel="noopener">
            {pr.title}
          </a>
        </h3>
        <span className="pr-author">@{pr.author}</span>
        {pr.is_draft && (
          <DraftButton owner={owner} repo={name} number={pr.number} />
        )}
        <ReviewedToggle pressed={isReviewed} onToggle={() => onToggleReviewed(key)} />
      </header>

      {showInlineStack && <PrStack nodes={pr.stack_nodes} />}

      <div className="pr-status">
        <div className="pr-status-row">
          <ChecksPill checks={pr.checks} />
          <Conflicts conflicts={pr.conflicts} />
        </div>

        <div className="pr-status-row">
          <CommentsPill human={pr.comments_human} bot={pr.comments_bot} />
          <ReviewerChip
            reviewer={reviewer}
            approved={pr.approved}
            reviewRequested={pr.review_requested}
            owner={owner}
            repo={name}
            number={pr.number}
          />
        </div>

        <div className="pr-status-row pr-status-row--actions">
          <WatchToggle
            pressed={isWatched}
            onToggle={() => onToggleWatch(key)}
            disabled={watchDisabled}
          />
          <NoteButton prKey={key} number={pr.number} />
          <CloudAgentLink prKey={key} repo={pr.repo} number={pr.number} />
          {pr.linear_url && (
            <a
              className="linear-link"
              href={pr.linear_url}
              target="_blank"
              rel="noopener"
              title="Open Linear ticket"
            >
              Linear &uarr;
            </a>
          )}
          <PreviewLink url={pr.preview_url} />
          {pr.column === "approved" && (
            <MergeButton
              owner={owner}
              repo={name}
              number={pr.number}
              title={pr.title}
              linearUrl={pr.linear_url}
            />
          )}
        </div>
      </div>
    </article>
  );
}
