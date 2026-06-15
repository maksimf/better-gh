import { useCallback, useMemo } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonArray } from "./storage";

const KEY = "better-gh.watched";

/**
 * "Watch" markers, keyed by "owner/repo#number". The backend poller
 * evaluates watched PRs after each GitHub refresh and publishes an
 * ntfy.sh notification when checks pass and a preview is ready, then
 * removes the watch automatically. Synced across devices via prefs.
 */
export function useWatchedKeys() {
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

  return { has, toggle, keys, hasAny: keys.length > 0 };
}

export function watchKey(repo: string, number: number): string {
  return `${repo}#${number}`;
}
