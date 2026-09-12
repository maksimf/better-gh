import { useMemo, useState, type ReactNode } from "react";

import type { ReviewPr } from "../api/types";
import { useNow } from "../hooks/useRelativeTime";
import { interleaveStacks } from "../stackGroups";
import { EmptyState } from "../ui/EmptyState";
import { DeferredSection } from "./DeferredSection";
import { DiffPanel } from "./DiffPanel";
import { ReviewRow } from "./ReviewRow";

function rowKey(pr: ReviewPr): string {
  return `${pr.repo}#${pr.number}`;
}

function splitRepo(repo: string): { owner: string; name: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, name: "" };
  return { owner: repo.slice(0, slash), name: repo.slice(slash + 1) };
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
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // Resolve the selected key against the current data so a PR that drops
  // off the list (e.g. after you approve it) closes the panel on its own.
  const selectedPr = useMemo(() => {
    if (!selectedKey) return null;
    return (
      [...reviews, ...deferredReviews].find((pr) => rowKey(pr) === selectedKey) ??
      null
    );
  }, [selectedKey, reviews, deferredReviews]);

  if (reviews.length === 0 && deferredReviews.length === 0) {
    return (
      <EmptyState
        variant="reviews"
        title="ALL CLEAR"
        subtitle="No PRs are waiting for your review."
      />
    );
  }

  function toggleSelect(pr: ReviewPr) {
    const key = rowKey(pr);
    setSelectedKey((cur) => (cur === key ? null : key));
  }

  const rowProps = {
    now,
    reviewedHas,
    onToggleReviewed,
    deferredHas,
    onToggleDeferred,
  };

  function renderRow(pr: ReviewPr, inStackGroup = false) {
    const key = rowKey(pr);
    return (
      <ReviewRow
        key={key}
        pr={pr}
        selected={key === selectedKey}
        onSelect={() => toggleSelect(pr)}
        inStackGroup={inStackGroup}
        {...rowProps}
      />
    );
  }

  function renderRows(items: ReviewPr[]): ReactNode[] {
    return interleaveStacks(items).map((entry) => {
      if (entry.kind === "item") return renderRow(entry.item);
      const { group } = entry;
      return (
        <div
          key={group.stackId}
          className="pr-stack-group"
          data-stack-id={group.stackId}
          aria-label={`Stack of ${group.cards.length} pull requests`}
        >
          {group.cards.map((pr) => renderRow(pr, true))}
        </div>
      );
    });
  }

  const split = selectedPr !== null;

  return (
    <div className={`reviews-layout${split ? " reviews-layout--split" : ""}`}>
      <div className="reviews-column">
        {reviews.length > 0 && (
          <div className="reviews-list" aria-live="polite">
            {renderRows(reviews)}
          </div>
        )}
        {deferredReviews.length > 0 && (
          <div className="reviews-list reviews-list--deferred-only">
            <DeferredSection count={deferredReviews.length}>
              {renderRows(deferredReviews)}
            </DeferredSection>
          </div>
        )}
      </div>

      {selectedPr && (
        <DiffPanel
          key={rowKey(selectedPr)}
          owner={splitRepo(selectedPr.repo).owner}
          repo={splitRepo(selectedPr.repo).name}
          number={selectedPr.number}
          title={selectedPr.title}
          url={selectedPr.url}
          author={selectedPr.author}
          onClose={() => setSelectedKey(null)}
        />
      )}
    </div>
  );
}
