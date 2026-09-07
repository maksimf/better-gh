import { useEffect, useMemo, useState } from "react";

import type { Column as ColumnKey, Pr } from "../api/types";
import { EmptyState } from "../ui/EmptyState";
import { BulkMergeButton } from "./BulkMergeButton";
import { Column } from "./Column";
import { MergeStackButton } from "./MergeStackButton";
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

type StackGroup = { stackId: string; cards: Pr[] };

/**
 * Pull every stacked PR out of the status columns and keep each stack
 * together (root first, then children in pre-order). First-seen order
 * across the incoming list is preserved so a newly opened stack doesn't
 * jump around on poll.
 */
function groupStacks(prs: Pr[]): StackGroup[] {
  const groups = new Map<string, Pr[]>();
  const order: string[] = [];
  for (const pr of prs) {
    if (!pr.stack_id) continue;
    let bucket = groups.get(pr.stack_id);
    if (!bucket) {
      bucket = [];
      groups.set(pr.stack_id, bucket);
      order.push(pr.stack_id);
    }
    bucket.push(pr);
  }
  return order.map((stackId) => ({
    stackId,
    cards: (groups.get(stackId) ?? []).sort(
      (a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0),
    ),
  }));
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

  const stackGroups = useMemo(() => groupStacks(prs), [prs]);
  const stackCount = stackGroups.length;

  const buckets: Record<ColumnKey, Pr[]> = {
    progress: [],
    ready: [],
    approved: [],
  };
  for (const pr of prs) {
    if (!pr.stack_id) buckets[pr.column].push(pr);
  }

  const stackedApproved = stackGroups.flatMap((group) =>
    group.cards.filter((pr) => pr.column === "approved"),
  );
  const allApprovedPrs = [...buckets.approved, ...stackedApproved];

  const [bulkSelected, setBulkSelected] = useState<Set<string>>(() => new Set());
  const approvedKeys = allApprovedPrs.map(rowKey);
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

  const selectedApprovedPrs = allApprovedPrs.filter((pr) =>
    bulkSelected.has(rowKey(pr)),
  );
  const allApprovedSelected =
    allApprovedPrs.length > 0 &&
    selectedApprovedPrs.length === allApprovedPrs.length;

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
      for (const pr of allApprovedPrs) {
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

  const counts: Record<ColumnKey, number> = {
    progress: buckets.progress.length,
    ready: buckets.ready.length,
    approved: buckets.approved.length,
  };
  const visibleCols = COLUMNS.filter((c) => counts[c] > 0).length;
  const hasStacks = stackCount > 0;
  const stacksWrap = hasStacks && visibleCols >= 3;
  const rowCols = hasStacks && !stacksWrap ? visibleCols + 1 : visibleCols;

  if (visibleCols === 0 && stackCount === 0 && deferredPrs.length === 0) {
    return (
      <EmptyState
        title="INBOX ZERO"
        subtitle="No open pull requests. Go touch grass."
      />
    );
  }

  const boardClass = [
    "board",
    rowCols === 1 && "board--cols-1",
    rowCols === 2 && "board--cols-2",
    rowCols === 3 && "board--cols-3",
    stacksWrap && "board--stacks-wrap",
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

  function renderCard(pr: Pr, bulkSelectable = false, inStackGroup = false) {
    const key = rowKey(pr);
    return (
      <PrCard
        key={key}
        pr={pr}
        selected={key === selectedKey}
        onSelect={() => setSelectedKey((cur) => (cur === key ? null : key))}
        bulkSelected={bulkSelectable ? bulkSelected.has(key) : undefined}
        onToggleBulkSelected={bulkSelectable ? () => toggleBulkPr(pr) : undefined}
        inStackGroup={inStackGroup}
        {...boardProps}
      />
    );
  }

  const bulkMergeActions =
    allApprovedPrs.length > 0 ? (
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
    ) : undefined;

  function renderStackGroups() {
    return stackGroups.map((group) => (
      <div
        key={group.stackId}
        className="pr-stack-group"
        data-stack-id={group.stackId}
      >
        <div className="pr-stack-group-header">
          <MergeStackButton
            prs={group.cards}
            onMerged={removeMergedSelections}
          />
        </div>
        {group.cards.map((pr) =>
          renderCard(pr, pr.column === "approved", true),
        )}
      </div>
    ));
  }

  if (selectedPr) {
    const { owner, name } = splitRepo(selectedPr.repo);
    return (
      <div className="reviews-layout reviews-layout--split">
        <div className="reviews-column">
          {COLUMNS.flatMap((column) =>
            buckets[column].map((pr) => renderCard(pr, column === "approved")),
          )}
          {stackCount > 0 && renderStackGroups()}
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
    visibleCols === 0 && stackCount === 0 ? null : (
      <div className={boardClass}>
        {COLUMNS.map((column) => (
          <Column
            key={column}
            column={column}
            count={counts[column]}
            hidden={counts[column] === 0}
            actions={column === "approved" ? bulkMergeActions : undefined}
          >
            {buckets[column].map((pr) =>
              renderCard(pr, column === "approved"),
            )}
          </Column>
        ))}
        {stackCount > 0 && (
          <Column
            column="stacks"
            count={stackCount}
            hidden={false}
            actions={
              buckets.approved.length === 0 ? bulkMergeActions : undefined
            }
          >
            {renderStackGroups()}
          </Column>
        )}
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
