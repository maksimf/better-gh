import { useCallback, useMemo } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonArray } from "./storage";

const KEY = "better-gh.manually-reviewed";

/**
 * Manually-reviewed marker, keyed by "owner/repo#number" so the same PR
 * stays marked across the MY PRs and REVIEWING tabs. Synced across the
 * viewer's devices via the preference store.
 */
export function useReviewedKeys() {
  const raw = useRawPref(KEY);
  const keys = useMemo(() => parseJsonArray(raw) ?? [], [raw]);
  const set = useMemo(() => new Set(keys), [keys]);

  const has = useCallback((key: string) => set.has(key), [set]);

  const toggle = useCallback(
    (key: string) => {
      const next = new Set(set);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      setRaw(KEY, JSON.stringify(Array.from(next)));
    },
    [set],
  );

  return { has, toggle };
}

export function reviewedKey(repo: string, number: number): string {
  return `${repo}#${number}`;
}
