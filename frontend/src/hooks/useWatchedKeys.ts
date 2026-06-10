import { useCallback, useMemo, useState } from "react";

import { readJsonArray, writeJsonArray } from "./storage";

const KEY = "better-gh.watched";

/**
 * "Watch" markers, keyed by "owner/repo#number". When a PR is watched we
 * publish an ntfy.sh notification the moment all of its checks turn green
 * (see useWatchNotifications). Pure client-side -- the server never sees it.
 */
export function useWatchedKeys() {
  const [keys, setKeys] = useState<string[]>(() => readJsonArray(KEY) ?? []);
  const set = useMemo(() => new Set(keys), [keys]);

  const has = useCallback((key: string) => set.has(key), [set]);

  const toggle = useCallback(
    (key: string) => {
      const next = new Set(set);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      const arr = Array.from(next);
      writeJsonArray(KEY, arr);
      setKeys(arr);
    },
    [set],
  );

  return { has, toggle, keys, hasAny: keys.length > 0 };
}

export function watchKey(repo: string, number: number): string {
  return `${repo}#${number}`;
}
