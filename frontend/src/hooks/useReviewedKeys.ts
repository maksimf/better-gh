import { useCallback, useMemo, useState } from "react";

import { readJsonArray, writeJsonArray } from "./storage";

const KEY = "better-gh.manually-reviewed";

/**
 * Manually-reviewed marker, keyed by "owner/repo#number" so the same PR
 * stays marked across the MY PRs and REVIEWING tabs. Pure client-side --
 * the server never sees it.
 */
export function useReviewedKeys() {
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

  return { has, toggle };
}

export function reviewedKey(repo: string, number: number): string {
  return `${repo}#${number}`;
}
