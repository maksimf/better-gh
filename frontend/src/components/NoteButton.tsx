import { useState } from "react";

import { usePrNotes } from "../hooks/usePrNotes";
import { CardToggle } from "../ui/CardToggle";
import { NoteModal } from "./NoteModal";
import { NoteIcon } from "./icons";

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
      <CardToggle
        variant="note"
        pressed={hasNote}
        title={title}
        onClick={() => setOpen(true)}
        icon={<NoteIcon />}
      />
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
