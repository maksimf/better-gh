import { useCallback, useRef } from "react";

import { useNotes } from "../hooks/useNotes";

export function NotesDrawer({
  open,
  onOpen,
  onClose,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
}) {
  const { notes, setNotes, clearNotes } = useNotes();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleOpen = useCallback(() => {
    onOpen();
    // Focus textarea after the drawer animates in
    setTimeout(() => textareaRef.current?.focus(), 50);
  }, [onOpen]);

  const handleClear = useCallback(() => {
    clearNotes();
    textareaRef.current?.focus();
  }, [clearNotes]);

  return (
    <>
      {/* Tab button at the right edge — hidden when drawer is open */}
      {!open && (
        <button
          type="button"
          className="notes-tab"
          aria-label="Open notes"
          onClick={handleOpen}
        >
          NOTES
        </button>
      )}

      {/* Drawer panel — slides in from the right */}
      <div
        className={`notes-drawer${open ? " notes-drawer--open" : ""}`}
        role="complementary"
        aria-label="Notes"
        aria-hidden={!open}
      >
        <div className="notes-drawer-header">
          <span className="notes-drawer-title">NOTES</span>
          <button
            type="button"
            className="notes-drawer-close"
            aria-label="Close notes"
            onClick={onClose}
          >
            &times;
          </button>
        </div>

        <textarea
          ref={textareaRef}
          className="notes-drawer-textarea"
          placeholder="Scratch pad — notes are synced across your devices…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          tabIndex={open ? 0 : -1}
        />

        <div className="notes-drawer-footer">
          <button
            type="button"
            className="notes-drawer-btn notes-drawer-btn--clear"
            onClick={handleClear}
            disabled={notes === ""}
          >
            CLEAR
          </button>
        </div>
      </div>
    </>
  );
}
