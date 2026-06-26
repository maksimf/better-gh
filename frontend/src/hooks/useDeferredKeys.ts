import { useCallback, useMemo } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonArray } from "./storage";
import { reviewedKey } from "./useReviewedKeys";

const KEY = "better-gh.deferred";

/**
 * Deferred marker, keyed by "owner/repo#number". Deferred PRs are hidden
 * from their normal column/list and shown in a collapsed section at the
 * bottom. Synced across devices via the preference store.
 */
export function useDeferredKeys() {
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

export { reviewedKey as deferredKey };
