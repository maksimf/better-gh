import { useCallback } from "react";

import { removeRaw, setRaw, useRawPref } from "./prefsStore";

const KEY = "better-gh.notes";

/**
 * Global scratch-pad notes, synced across the viewer's devices via the
 * server prefs store (SQLite). Distinct from per-PR notes (usePrNotes).
 */
export function useNotes(): {
  notes: string;
  setNotes: (value: string) => void;
  clearNotes: () => void;
} {
  const raw = useRawPref(KEY);
  const notes = raw ?? "";

  const setNotes = useCallback((value: string) => {
    if (value === "") {
      removeRaw(KEY);
      return;
    }
    setRaw(KEY, value);
  }, []);

  const clearNotes = useCallback(() => {
    removeRaw(KEY);
  }, []);

  return { notes, setNotes, clearNotes };
}
