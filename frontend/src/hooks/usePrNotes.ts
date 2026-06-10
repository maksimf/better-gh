import { useCallback, useMemo } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonRecord } from "./storage";

const KEY = "better-gh.pr-notes";

/**
 * Per-PR personal notes, keyed by "owner/repo#number" -> note text.
 * Synced across the viewer's devices via the preference store.
 */
export function usePrNotes() {
  const raw = useRawPref(KEY);
  const map = useMemo(() => parseJsonRecord(raw) ?? {}, [raw]);

  const get = useCallback((key: string): string | null => map[key] ?? null, [map]);

  const has = useCallback(
    (key: string): boolean => Boolean(map[key]?.trim()),
    [map],
  );

  const set = useCallback(
    (key: string, note: string) => {
      const trimmed = note.trim();
      if (!trimmed) {
        if (!(key in map)) return;
        const next = { ...map };
        delete next[key];
        setRaw(KEY, JSON.stringify(next));
        return;
      }
      setRaw(KEY, JSON.stringify({ ...map, [key]: trimmed }));
    },
    [map],
  );

  const remove = useCallback(
    (key: string) => {
      if (!(key in map)) return;
      const next = { ...map };
      delete next[key];
      setRaw(KEY, JSON.stringify(next));
    },
    [map],
  );

  return { get, has, set, remove };
}
