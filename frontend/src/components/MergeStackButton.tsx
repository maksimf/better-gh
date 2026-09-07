import { useState } from "react";

import type { Pr } from "../api/types";
import { useStackMergePr } from "../api/queries";
import { reviewedKey } from "../hooks/useReviewedKeys";
import { ActionButton } from "../ui/ActionButton";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { useTransientError } from "../ui/useTransientError";

function splitRepo(repo: string): { owner: string; repo: string } {
  const slash = repo.indexOf("/");
  if (slash < 0) return { owner: repo, repo: "" };
  return { owner: repo.slice(0, slash), repo: repo.slice(slash + 1) };
}

/** Root first (lowest stack_order), then each child toward the leaf. */
function orderRootFirst(prs: Pr[]): Pr[] {
  return [...prs].sort((a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0));
}

export function MergeStackButton({
  prs,
  onMerged,
}: {
  prs: Pr[];
  onMerged: (keys: string[]) => void;
}) {
  const merge = useStackMergePr();
  const [open, setOpen] = useState(false);
  const { error, showError, clearError } = useTransientError(5000);
  const orderedPrs = orderRootFirst(prs);

  function doMerge() {
    clearError();
    merge.mutate(
      orderedPrs.map((pr) => ({ ...splitRepo(pr.repo), number: pr.number })),
      {
        onSuccess: (result) => {
          const results = result?.results ?? [];
          const mergedKeys = results
            .filter((item) => item.merged)
            .map((item) =>
              reviewedKey(`${item.owner}/${item.repo}`, item.number),
            );
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
      <ActionButton
        kind="bulk-merge"
        className="merge-stack-button"
        error={Boolean(error)}
        title={error ?? "Merge this stack from the root, without waiting for CI"}
        disabled={prs.length === 0 || merge.isPending}
        onClick={() => setOpen(true)}
      >
        MERGE STACK{" "}
        <span className="bulk-merge-count">{prs.length}</span>
      </ActionButton>

      <Dialog
        open={open}
        onClose={() => {
          if (!merge.isPending) setOpen(false);
        }}
        className="merge-modal bulk-merge-modal"
        ariaLabelledBy="stack-merge-modal-title"
        blockBackdropClose={merge.isPending}
      >
        <header className="merge-modal-header">
          <h2 id="stack-merge-modal-title" className="merge-modal-title">
            MERGE STACK
          </h2>
          <Button
            surface="close"
            modal="merge"
            ariaLabel="Cancel"
            disabled={merge.isPending}
            onClick={() => setOpen(false)}
          >
            &times;
          </Button>
        </header>

        <div className="merge-modal-body">
          <p className="merge-modal-summary">
            Merge this stack from the root, then each child, without
            waiting for CI. A failed merge stops the rest of the stack.
          </p>
          <ul className="bulk-merge-list">
            {orderedPrs.map((pr) => (
              <li key={reviewedKey(pr.repo, pr.number)}>
                <strong>
                  {pr.repo}#{pr.number}
                </strong>
                <span>{pr.title}</span>
              </li>
            ))}
          </ul>
        </div>

        <footer className="merge-modal-footer">
          <Button
            surface="modal"
            modal="merge"
            variant="ghost"
            disabled={merge.isPending}
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            surface="modal"
            modal="merge"
            variant="merge"
            disabled={merge.isPending}
            onClick={doMerge}
          >
            {merge.isPending ? "Merging…" : `Merge stack (${prs.length})`}
          </Button>
        </footer>
      </Dialog>
    </>
  );
}