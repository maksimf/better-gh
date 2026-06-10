import type { CSSProperties, ReactNode } from "react";

import type { Pr } from "../api/types";
import { useCloudAgents } from "../hooks/useCloudAgents";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { ChecksPill, Conflicts } from "./ChecksPill";
import { CloudAgentLink } from "./CloudAgentLink";
import { CommentsPill } from "./CommentsPill";
import { DraftButton } from "./DraftButton";
import { MergeButton } from "./MergeButton";
import { NoteButton } from "./NoteButton";
import { OverflowMenu } from "./OverflowMenu";
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

  // A QA agent that's already linked is meaningful status -> show its badge
  // inline. When none is linked the launch/link controls are tucked into the
  // overflow menu so they don't crowd the resting card.
  const { get: getAgent } = useCloudAgents();
  const linkedAgent = getAgent(key);

  // One primary call-to-action per card, by precedence: merge an approved PR,
  // else promote a draft, else request review when it hasn't been asked for.
  let primaryAction: ReactNode = null;
  if (pr.column === "approved") {
    primaryAction = (
      <MergeButton
        owner={owner}
        repo={name}
        number={pr.number}
        title={pr.title}
        linearUrl={pr.linear_url}
      />
    );
  } else if (pr.is_draft) {
    primaryAction = <DraftButton owner={owner} repo={name} number={pr.number} />;
  } else {
    // Null unless the PR is genuinely awaiting a review request.
    primaryAction = (
      <ReviewerChip
        variant="action"
        reviewer={reviewer}
        approved={pr.approved}
        reviewRequested={pr.review_requested}
        owner={owner}
        repo={name}
        number={pr.number}
      />
    );
  }

  const showOverflow = !linkedAgent;

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
        {primaryAction && <div className="pr-primary">{primaryAction}</div>}
      </header>

      {showInlineStack && <PrStack nodes={pr.stack_nodes} />}

      <div className="pr-bar">
        {pr.is_draft && <span className="pr-tag pr-tag--draft">Draft</span>}
        <ChecksPill checks={pr.checks} />
        <Conflicts conflicts={pr.conflicts} />
        <CommentsPill
          human={pr.comments_human}
          bot={pr.comments_bot}
          prRef={{ owner, repo: name, number: pr.number }}
        />
        <div className="pr-toggles">
          <ReviewedToggle pressed={isReviewed} onToggle={() => onToggleReviewed(key)} />
          <WatchToggle
            pressed={isWatched}
            onToggle={() => onToggleWatch(key)}
            disabled={watchDisabled}
          />
          <NoteButton prKey={key} number={pr.number} />
          {showOverflow && (
            <OverflowMenu>
              <CloudAgentLink prKey={key} repo={pr.repo} number={pr.number} />
            </OverflowMenu>
          )}
        </div>
        <ReviewerChip
          variant="chip"
          reviewer={reviewer}
          approved={pr.approved}
          reviewRequested={pr.review_requested}
          owner={owner}
          repo={name}
          number={pr.number}
        />
      </div>

      <div className="pr-links">
        <PreviewLink url={pr.preview_url} />
        {pr.linear_url && (
          <a
            className="linear-link"
            href={pr.linear_url}
            target="_blank"
            rel="noopener"
            title="Open Linear ticket"
          >
            Linear
          </a>
        )}
        {linkedAgent && (
          <CloudAgentLink prKey={key} repo={pr.repo} number={pr.number} />
        )}
      </div>

    </article>
  );
}
