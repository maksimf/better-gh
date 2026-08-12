import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

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
  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="merge-modal"
      ariaLabelledBy="merge-modal-title"
      blockBackdropClose={pending}
    >
      <header className="merge-modal-header">
        <h2 id="merge-modal-title" className="merge-modal-title">
          MERGE PR
        </h2>
        <Button
          surface="close"
          modal="merge"
          ariaLabel="Cancel"
          disabled={pending}
          onClick={onClose}
        >
          &times;
        </Button>
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
        <Button
          surface="modal"
          modal="merge"
          variant="ghost"
          disabled={pending}
          onClick={onClose}
        >
          Cancel
        </Button>
        <Button
          surface="modal"
          modal="merge"
          variant="merge"
          disabled={pending}
          onClick={onJustMerge}
        >
          Just merge
        </Button>
        {linearTicket && (
          <Button
            surface="modal"
            modal="merge"
            variant="linear"
            disabled={pending}
            onClick={onMergeAndLinear}
          >
            Merge &amp; mark {linearTicket} done
          </Button>
        )}
      </footer>
    </Dialog>
  );
}
