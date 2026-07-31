import { Fragment, useEffect, useMemo, useState } from "react";

import type { Column as ColumnKey, Pr } from "../api/types";
import { BulkMergeButton } from "./BulkMergeButton";
import { Column } from "./Column";
import { DeferredSection } from "./DeferredSection";
import { DiffPanel } from "./DiffPanel";
import { PrCard } from "./PrCard";

const COLUMNS: ColumnKey[] = ["progress", "ready", "approved"];

function rowKey(pr: Pr): string {
  return `${pr.repo}#${pr.number}`;
}

function splitRepo(repo: string): { owner: string; name: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, name: "" };
  return { owner: repo.slice(0, slash), name: repo.slice(slash + 1) };
}

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
  reviewedHas: (key: string) => boolean;
  onToggleReviewed: (key: string) => void;
  deferredHas: (key: string) => boolean;
  onToggleDeferred: (key: string) => void;
  watchedHas: (key: string) => boolean;
  onToggleWatch: (key: string) => void;
  watchDisabled: boolean;
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selectedPr = useMemo(() => {
    if (!selectedKey) return null;
    return (
      [...prs, ...deferredPrs].find((pr) => rowKey(pr) === selectedKey) ?? null
    );
  }, [selectedKey, prs, deferredPrs]);

  const buckets: Record<ColumnKey, Pr[]> = {
    progress: [],
    ready: [],
    approved: [],
  };
  for (const pr of prs) buckets[pr.column].push(pr);

  const [bulkSelected, setBulkSelected] = useState<Set<string>>(() => new Set());
  const approvedKeys = buckets.approved.map(rowKey);
  const approvedKeySignature = approvedKeys.join("\0");
  useEffect(() => {
    const visible = new Set(
      approvedKeySignature ? approvedKeySignature.split("\0") : [],
    );
    setBulkSelected((current) => {
      const next = new Set([...current].filter((key) => visible.has(key)));
      return next.size === current.size ? current : next;
    });
  }, [approvedKeySignature]);

  const selectedApprovedPrs = buckets.approved.filter((pr) =>
    bulkSelected.has(rowKey(pr)),
  );
  const allApprovedSelected =
    buckets.approved.length > 0 &&
    selectedApprovedPrs.length === buckets.approved.length;

  function toggleBulkPr(pr: Pr) {
    const key = rowKey(pr);
    setBulkSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAllApproved() {
    setBulkSelected((current) => {
      const next = new Set(current);
      for (const pr of buckets.approved) {
        const key = rowKey(pr);
        if (allApprovedSelected) next.delete(key);
        else next.add(key);
      }
      return next;
    });
  }

  function removeMergedSelections(keys: string[]) {
    if (keys.length === 0) return;
    setBulkSelected((current) => {
      const next = new Set(current);
      for (const key of keys) next.delete(key);
      return next;
    });
  }

  const allCardsFlat = useMemo(() => {
    const flat: Pr[] = [];
    for (const column of COLUMNS) {
      for (const item of groupColumn(buckets[column])) {
        if (item.kind === "card") {
          flat.push(item.pr);
        } else {
          flat.push(...item.cards);
        }
      }
    }
    return flat;
  }, [prs]);

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
    reviewedHas,
    onToggleReviewed,
    deferredHas,
    onToggleDeferred,
    watchedHas,
    onToggleWatch,
    watchDisabled,
  };

  function renderCard(pr: Pr, bulkSelectable = false) {
    const key = rowKey(pr);
    return (
      <PrCard
        key={key}
        pr={pr}
        selected={key === selectedKey}
        onSelect={() => setSelectedKey((cur) => (cur === key ? null : key))}
        bulkSelected={bulkSelectable ? bulkSelected.has(key) : undefined}
        onToggleBulkSelected={bulkSelectable ? () => toggleBulkPr(pr) : undefined}
        {...boardProps}
      />
    );
  }

  if (selectedPr) {
    const { owner, name } = splitRepo(selectedPr.repo);
    return (
      <div className="reviews-layout reviews-layout--split">
        <div className="reviews-column">
          {allCardsFlat.map((pr) =>
            renderCard(pr, pr.column === "approved"),
          )}
          {deferredPrs.length > 0 && (
            <DeferredSection count={deferredPrs.length}>
              {deferredPrs.map((pr) => renderCard(pr))}
            </DeferredSection>
          )}
        </div>
        <DiffPanel
          key={rowKey(selectedPr)}
          owner={owner}
          repo={name}
          number={selectedPr.number}
          title={selectedPr.title}
          url={selectedPr.url}
          author={selectedPr.author}
          onClose={() => setSelectedKey(null)}
        />
      </div>
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
            actions={
              column === "approved" ? (
                <div className="bulk-merge-actions">
                  <label className="bulk-select-all">
                    <input
                      type="checkbox"
                      checked={allApprovedSelected}
                      onChange={toggleAllApproved}
                    />
                    <span>ALL</span>
                  </label>
                  <BulkMergeButton
                    prs={selectedApprovedPrs}
                    onMerged={removeMergedSelections}
                  />
                </div>
              ) : undefined
            }
          >
            {groupColumn(buckets[column]).map((item) =>
              item.kind === "card" ? (
                renderCard(item.pr, column === "approved")
              ) : (
                <div
                  key={item.stackId}
                  className="pr-stack-group"
                  data-stack-id={item.stackId}
                >
                  {item.cards.map((pr) => (
                    <Fragment key={`${pr.repo}#${pr.number}`}>
                      {renderCard(pr, column === "approved")}
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
