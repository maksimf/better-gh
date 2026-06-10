import { useState } from "react";

import { usePrNotes } from "../hooks/usePrNotes";
import { NoteModal } from "./NoteModal";

/**
 * Per-PR note control. Opens a modal to add or edit a personal note stored
 * in localStorage. The button highlights when a note exists.
 */
export function NoteButton({ prKey, number }: { prKey: string; number: number }) {
  const { get, has, set } = usePrNotes();
  const [open, setOpen] = useState(false);
  const hasNote = has(prKey);
  const title = hasNote
    ? "Edit your personal note for this PR"
    : "Add a personal note for this PR";

  return (
    <>
      <button
        type="button"
        className="note-button"
        title={title}
        aria-label={title}
        aria-pressed={hasNote}
        onClick={() => setOpen(true)}
      >
        Note
      </button>
      <NoteModal
        open={open}
        number={number}
        initialNote={get(prKey) ?? ""}
        onSave={(note) => {
          set(prKey, note);
          setOpen(false);
        }}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
