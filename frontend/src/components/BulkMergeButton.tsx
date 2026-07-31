import { useEffect, useRef, useState } from "react";

import type { Pr } from "../api/types";
import { useBulkMergePr } from "../api/queries";
import { reviewedKey } from "../hooks/useReviewedKeys";

function splitRepo(repo: string): { owner: string; repo: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, repo: "" };
  return { owner: repo.slice(0, slash), repo: repo.slice(slash + 1) };
}

/** Merge stack children before their parents so the root lands everything. */
function orderForMerge(prs: Pr[]): Pr[] {
  const stacks = new Map<string, Pr[]>();
  for (const pr of prs) {
    if (!pr.stack_id) continue;
    const stack = stacks.get(pr.stack_id) ?? [];
    stack.push(pr);
    stacks.set(pr.stack_id, stack);
  }

  const emittedStacks = new Set<string>();
  const ordered: Pr[] = [];
  for (const pr of prs) {
    if (!pr.stack_id) {
      ordered.push(pr);
      continue;
    }
    if (emittedStacks.has(pr.stack_id)) continue;
    emittedStacks.add(pr.stack_id);
    ordered.push(
      ...(stacks.get(pr.stack_id) ?? []).sort(
        (a, b) => (b.stack_order ?? 0) - (a.stack_order ?? 0),
      ),
    );
  }
  return ordered;
}

export function BulkMergeButton({
  prs,
  onMerged,
}: {
  prs: Pr[];
  onMerged: (keys: string[]) => void;
}) {
  const merge = useBulkMergePr();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const orderedPrs = orderForMerge(prs);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  function showError(message: string) {
    setError(message);
    window.setTimeout(() => setError(null), 5000);
  }

  function doMerge() {
    setError(null);
    merge.mutate(
      orderedPrs.map((pr) => ({ ...splitRepo(pr.repo), number: pr.number })),
      {
        onSuccess: (result) => {
          const results = result?.results ?? [];
          const mergedKeys = results
            .filter((item) => item.merged)
            .map((item) => reviewedKey(`${item.owner}/${item.repo}`, item.number));
          const failed = results.filter((item) => !item.merged);

          onMerged(mergedKeys);
          setOpen(false);
          if (failed.length > 0) {
            const first = failed[0];
            showError(
              failed.length === 1
                ? `#${first.number} failed: ${first.error ?? "merge failed"}`
                : `${failed.length} PRs failed to merge`,
            );
          }
        },
        onError: (cause) => {
          setOpen(false);
          showError(cause instanceof Error ? cause.message : String(cause));
        },
      },
    );
  }

  return (
    <>
      <button
        type="button"
        className={`bulk-merge-button${error ? " is-error" : ""}`}
        title={error ?? "Merge all selected pull requests"}
        disabled={prs.length === 0 || merge.isPending}
        onClick={() => setOpen(true)}
      >
        MERGE ALL <span className="bulk-merge-count">{prs.length}</span>
      </button>

      <dialog
        ref={dialogRef}
        className="merge-modal bulk-merge-modal"
        aria-labelledby="bulk-merge-modal-title"
        onClose={() => {
          if (!merge.isPending) setOpen(false);
        }}
        onClick={(event) => {
          if (event.target === dialogRef.current && !merge.isPending) setOpen(false);
        }}
      >
        <header className="merge-modal-header">
          <h2 id="bulk-merge-modal-title" className="merge-modal-title">
            MERGE SELECTED PRS
          </h2>
          <button
            type="button"
            className="merge-modal-close"
            aria-label="Cancel"
            disabled={merge.isPending}
            onClick={() => setOpen(false)}
          >
            &times;
          </button>
        </header>

        <div className="merge-modal-body">
          <p className="merge-modal-summary">
            Merge all <strong>{prs.length}</strong> selected pull requests?
            Each PR is attempted even if another merge fails.
          </p>
          <ul className="bulk-merge-list">
            {orderedPrs.map((pr) => (
              <li key={reviewedKey(pr.repo, pr.number)}>
                <strong>{pr.repo}#{pr.number}</strong>
                <span>{pr.title}</span>
              </li>
            ))}
          </ul>
        </div>

        <footer className="merge-modal-footer">
          <button
            type="button"
            className="merge-modal-btn merge-modal-btn--ghost"
            disabled={merge.isPending}
            onClick={() => setOpen(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className="merge-modal-btn merge-modal-btn--merge"
            disabled={merge.isPending}
            onClick={doMerge}
          >
            {merge.isPending ? "Merging…" : `Merge all ${prs.length}`}
          </button>
        </footer>
      </dialog>
    </>
  );
}
