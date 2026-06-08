import { useEffect, useRef } from "react";

/**
 * Confirmation dialog for the per-card MERGE button.
 *
 * Replaces the old `window.confirm` so we can offer a second, richer
 * action: merging *and* moving the PR's linked Linear ticket into its
 * team's "Done" state in one click. The Linear option only appears when
 * the PR actually has a linked ticket (`linearTicket`).
 */
export function MergeModal({
  open,
  title,
  number,
  linearTicket,
  pending,
  onJustMerge,
  onMergeAndLinear,
  onClose,
}: {
  open: boolean;
  title: string;
  number: number;
  linearTicket: string | null;
  pending: boolean;
  onJustMerge: () => void;
  onMergeAndLinear: () => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="merge-modal"
      aria-labelledby="merge-modal-title"
      onClose={onClose}
      onClick={(e) => {
        // Backdrop click (lands on the <dialog> itself) closes.
        if (e.target === dialogRef.current && !pending) onClose();
      }}
    >
      <header className="merge-modal-header">
        <h2 id="merge-modal-title" className="merge-modal-title">
          MERGE PR
        </h2>
        <button
          type="button"
          className="merge-modal-close"
          aria-label="Cancel"
          disabled={pending}
          onClick={onClose}
        >
          &times;
        </button>
      </header>

      <div className="merge-modal-body">
        <p className="merge-modal-summary">
          Merge <span className="merge-modal-pr">#{number}</span>{" "}
          <span className="merge-modal-pr-title">{title}</span> into the base
          branch?
        </p>
        {linearTicket && (
          <p className="merge-modal-hint">
            Linked Linear ticket:{" "}
            <strong className="merge-modal-ticket">{linearTicket}</strong>
          </p>
        )}
      </div>

      <footer className="merge-modal-footer">
        <button
          type="button"
          className="merge-modal-btn merge-modal-btn--ghost"
          disabled={pending}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="merge-modal-btn merge-modal-btn--merge"
          disabled={pending}
          onClick={onJustMerge}
        >
          Just merge
        </button>
        {linearTicket && (
          <button
            type="button"
            className="merge-modal-btn merge-modal-btn--linear"
            disabled={pending}
            onClick={onMergeAndLinear}
          >
            Merge &amp; mark {linearTicket} done
          </button>
        )}
      </footer>
    </dialog>
  );
}
