import { useEffect, useState } from "react";

import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

/**
 * Modal for adding or editing a personal note on a PR. Notes are stored
 * client-side in localStorage and are only visible to this browser.
 */
export function NoteModal({
  open,
  number,
  initialNote,
  onSave,
  onClose,
}: {
  open: boolean;
  number: number;
  initialNote: string;
  onSave: (note: string) => void;
  onClose: () => void;
}) {
  const [note, setNote] = useState(initialNote);

  useEffect(() => {
    if (open) setNote(initialNote);
  }, [open, initialNote]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="note-modal"
      ariaLabelledBy="note-modal-title"
    >
      <div
        onClick={(e) => {
          // Preserve legacy stopPropagation so card click handlers don't fire.
          e.stopPropagation();
        }}
      >
        <header className="note-modal-header">
          <h2 id="note-modal-title" className="note-modal-title">
            PR NOTE
          </h2>
          <Button
            surface="close"
            modal="note"
            ariaLabel="Cancel"
            onClick={onClose}
          >
            &times;
          </Button>
        </header>

        <div className="note-modal-body">
          <p className="note-modal-summary">
            Add a personal note for{" "}
            <span className="note-modal-pr">#{number}</span>. Only you can see
            this on this device.
          </p>
          <label className="note-modal-label" htmlFor="note-modal-text">
            NOTE
          </label>
          <textarea
            id="note-modal-text"
            className="note-modal-textarea"
            rows={5}
            value={note}
            placeholder="Context, blockers, follow-ups…"
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        <footer className="note-modal-footer">
          {initialNote.trim() && (
            <Button
              surface="modal"
              modal="note"
              variant="danger"
              onClick={() => onSave("")}
            >
              Delete
            </Button>
          )}
          <span className="note-modal-footer-spacer" />
          <Button
            surface="modal"
            modal="note"
            variant="ghost"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            surface="modal"
            modal="note"
            variant="save"
            onClick={() => onSave(note)}
          >
            Save
          </Button>
        </footer>
      </div>
    </Dialog>
  );
}
