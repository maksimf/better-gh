import { useEffect, useRef, useState } from "react";

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
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [note, setNote] = useState(initialNote);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  useEffect(() => {
    if (open) setNote(initialNote);
  }, [open, initialNote]);

  return (
    <dialog
      ref={dialogRef}
      className="note-modal"
      aria-labelledby="note-modal-title"
      onClose={onClose}
      onClick={(e) => {
        e.stopPropagation();
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <header className="note-modal-header">
        <h2 id="note-modal-title" className="note-modal-title">
          PR NOTE
        </h2>
        <button
          type="button"
          className="note-modal-close"
          aria-label="Cancel"
          onClick={onClose}
        >
          &times;
        </button>
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
          <button
            type="button"
            className="note-modal-btn note-modal-btn--danger"
            onClick={() => onSave("")}
          >
            Delete
          </button>
        )}
        <span className="note-modal-footer-spacer" />
        <button
          type="button"
          className="note-modal-btn note-modal-btn--ghost"
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="note-modal-btn note-modal-btn--save"
          onClick={() => onSave(note)}
        >
          Save
        </button>
      </footer>
    </dialog>
  );
}
