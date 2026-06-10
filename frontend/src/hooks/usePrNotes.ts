import { useCallback, useState } from "react";

import { readJsonRecord, writeJsonRecord } from "./storage";

const KEY = "better-gh.pr-notes";

/**
 * Per-PR personal notes, keyed by "owner/repo#number" -> note text.
 * Client-side only, like watched/reviewed markers and cloud-agent links.
 */
export function usePrNotes() {
  const [map, setMap] = useState<Record<string, string>>(
    () => readJsonRecord(KEY) ?? {},
  );

  const get = useCallback((key: string): string | null => map[key] ?? null, [map]);

  const has = useCallback(
    (key: string): boolean => Boolean(map[key]?.trim()),
    [map],
  );

  const set = useCallback((key: string, note: string) => {
    setMap((prev) => {
      const trimmed = note.trim();
      if (!trimmed) {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        writeJsonRecord(KEY, next);
        return next;
      }
      const next = { ...prev, [key]: trimmed };
      writeJsonRecord(KEY, next);
      return next;
    });
  }, []);

  const remove = useCallback((key: string) => {
    setMap((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      writeJsonRecord(KEY, next);
      return next;
    });
  }, []);

  return { get, has, set, remove };
}
