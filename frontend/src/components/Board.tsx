import { Fragment } from "react";

import type { Column as ColumnKey, Pr } from "../api/types";
import { Column } from "./Column";
import { DeferredSection } from "./DeferredSection";
import { PrCard } from "./PrCard";

const COLUMNS: ColumnKey[] = ["progress", "ready", "approved"];

type GroupItem =
  | { kind: "card"; pr: Pr }
  | { kind: "group"; stackId: string; cards: Pr[] };

/**
 * Arrange a column so co-column stack cards sit next to each other (root
 * first, then children in pre-order) inside a .pr-stack-group wrapper.
 * Bare cards keep their position relative to whichever stack-group
 * appeared first. Ports the old groupStacks() pass.
 */
function groupColumn(prs: Pr[]): GroupItem[] {
  const groups = new Map<string, Pr[]>();
  const ordered: GroupItem[] = [];
  for (const pr of prs) {
    if (pr.stack_id && pr.stack_co_column) {
      let bucket = groups.get(pr.stack_id);
      if (!bucket) {
        bucket = [];
        groups.set(pr.stack_id, bucket);
        ordered.push({ kind: "group", stackId: pr.stack_id, cards: bucket });
      }
      bucket.push(pr);
    } else {
      ordered.push({ kind: "card", pr });
    }
  }
  for (const bucket of groups.values()) {
    bucket.sort((a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0));
  }
  return ordered;
}

function EmptyState() {
  return (
    <section className="empty-state" aria-live="polite">
      <div className="empty-state-mark" aria-hidden="true">
        <span className="shape shape--circle"></span>
        <span className="shape shape--square"></span>
        <span className="shape shape--triangle"></span>
      </div>
      <h2 className="empty-state-title">INBOX ZERO</h2>
      <p className="empty-state-sub">No open pull requests. Go touch grass.</p>
    </section>
  );
}

export function Board({
  prs,
  deferredPrs,
  reviewer,
  reviewedHas,
  onToggleReviewed,
  deferredHas,
  onToggleDeferred,
  watchedHas,
  onToggleWatch,
  watchDisabled,
}: {
  prs: Pr[];
  deferredPrs: Pr[];
  reviewer: string;
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  deferredHas: (key: string) => boolean;
  onToggleDeferred: (key: string) => void;
  watchedHas: (key: string) => boolean;
  onToggleWatch: (key: string) => void;
  watchDisabled: boolean;
}) {
  const buckets: Record<ColumnKey, Pr[]> = {
    progress: [],
    ready: [],
    approved: [],
  };
  for (const pr of prs) buckets[pr.column].push(pr);

  const counts: Record<ColumnKey, number> = {
    progress: buckets.progress.length,
    ready: buckets.ready.length,
    approved: buckets.approved.length,
  };
  const visibleCols = COLUMNS.filter((c) => counts[c] > 0).length;

  if (visibleCols === 0 && deferredPrs.length === 0) return <EmptyState />;

  const boardClass = [
    "board",
    visibleCols === 1 && "board--cols-1",
    visibleCols === 2 && "board--cols-2",
    visibleCols === 3 && "board--cols-3",
  ]
    .filter(Boolean)
    .join(" ");

  const boardProps = {
    reviewer,
    reviewedHas,
    onToggleReviewed,
    deferredHas,
    onToggleDeferred,
    watchedHas,
    onToggleWatch,
    watchDisabled,
  };

  function renderCard(pr: Pr) {
    return (
      <PrCard
        key={`${pr.repo}#${pr.number}`}
        pr={pr}
        {...boardProps}
      />
    );
  }

  const board =
    visibleCols === 0 ? null : (
      <div className={boardClass}>
        {COLUMNS.map((column) => (
          <Column
            key={column}
            column={column}
            count={counts[column]}
            hidden={counts[column] === 0}
          >
            {groupColumn(buckets[column]).map((item) =>
              item.kind === "card" ? (
                renderCard(item.pr)
              ) : (
                <div
                  key={item.stackId}
                  className="pr-stack-group"
                  data-stack-id={item.stackId}
                >
                  {item.cards.map((pr) => (
                    <Fragment key={`${pr.repo}#${pr.number}`}>
                      {renderCard(pr)}
                    </Fragment>
                  ))}
                </div>
              ),
            )}
          </Column>
        ))}
      </div>
    );

  return (
    <>
      {board}
      {deferredPrs.length > 0 && (
        <DeferredSection count={deferredPrs.length}>
          {deferredPrs.map((pr) => renderCard(pr))}
        </DeferredSection>
      )}
    </>
  );
}
