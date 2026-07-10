import type { CSSProperties, ReactNode } from "react";
import { marked } from "marked";

import type { Pr } from "../api/types";
import { useCloudAgents } from "../hooks/useCloudAgents";
import { usePrNotes } from "../hooks/usePrNotes";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { ChecksPill, Conflicts } from "./ChecksPill";
import { CloudAgentLink } from "./CloudAgentLink";
import { CommentsPill } from "./CommentsPill";
import { DeferredToggle } from "./DeferredToggle";
import { DraftButton } from "./DraftButton";
import { MergeButton } from "./MergeButton";
import { NoteButton } from "./NoteButton";
import { OverflowMenu } from "./OverflowMenu";
import { PrLocStats } from "./PrLocStats";
import { PrStack } from "./PrStack";
import { PreviewLink } from "./PreviewLink";
import { ReviewedToggle } from "./ReviewedToggle";
import { RequestReviewAction, ReviewerChips } from "./ReviewerChip";
import { WatchToggle } from "./WatchToggle";

function splitRepo(repo: string): { owner: string; name: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, name: "" };
  return { owner: repo.slice(0, slash), name: repo.slice(slash + 1) };
}

export function PrCard({
  pr,
  reviewedHas,
  onToggleReviewed,
  deferredHas,
  onToggleDeferred,
  watchedHas,
  onToggleWatch,
  watchDisabled,
  selected,
  onSelect,
}: {
  pr: Pr;
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  deferredHas: (key: string) => boolean;
  onToggleDeferred: (key: string) => void;
  watchedHas: (key: string) => boolean;
  onToggleWatch: (key: string) => void;
  watchDisabled: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const { owner, name } = splitRepo(pr.repo);
  const key = reviewedKey(pr.repo, pr.number);
  const isReviewed = reviewedHas(key);
  const isDeferred = deferredHas(key);
  const isWatched = watchedHas(key);
  const showInlineStack = pr.stack_nodes.length > 0 && !pr.stack_co_column;

  // A QA agent that's already linked is meaningful status -> show its badge
  // inline. When none is linked the launch/link controls are tucked into the
  // overflow menu so they don't crowd the resting card.
  const { get: getAgent } = useCloudAgents();
  const { get: getNote } = usePrNotes();
  const linkedAgent = getAgent(key);
  const note = getNote(key);

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
    // Null unless the PR is genuinely awaiting a review request from at
    // least one tracked reviewer.
    primaryAction = (
      <RequestReviewAction
        reviewers={pr.reviewers}
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
    selected && "is-selected",
  ]
    .filter(Boolean)
    .join(" ");

  const style: CSSProperties | undefined = pr.stack_co_column
    ? ({ "--stack-depth": pr.stack_depth ?? 0 } as CSSProperties)
    : undefined;

  return (
    <article
      className={classes}
      data-repo={pr.repo}
      data-column={pr.column}
      style={style}
    >
      <div className="pr-card-body">
        <header className={`pr-head${note ? " pr-head--has-note" : ""}`}>
          <a className="pr-number" href={pr.url} target="_blank" rel="noopener">
            #{pr.number}
          </a>
          <div className="pr-head-main">
            <h3 className="pr-title">
              <a href={pr.url} target="_blank" rel="noopener">
                {pr.title}
              </a>
              <PrLocStats additions={pr.additions} deletions={pr.deletions} />
            </h3>
            {note && (
              <p
                className="pr-note"
                title={note}
                // eslint-disable-next-line react/no-danger
                dangerouslySetInnerHTML={{ __html: marked.parseInline(note) as string }}
              />
            )}
          </div>
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
            <DeferredToggle pressed={isDeferred} onToggle={() => onToggleDeferred(key)} />
            {showOverflow && (
              <OverflowMenu>
                <CloudAgentLink prKey={key} repo={pr.repo} number={pr.number} />
              </OverflowMenu>
            )}
          </div>
          <ReviewerChips
            reviewers={pr.reviewers}
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
      </div>

      <button
        type="button"
        className={`pr-open-code${selected ? " is-active" : ""}`}
        title={selected ? "Hide code" : "Open code"}
        aria-label={selected ? "Hide code" : "Open code"}
        aria-pressed={selected}
        onClick={onSelect}
      >
        <span aria-hidden="true">→</span>
      </button>
    </article>
  );
}
