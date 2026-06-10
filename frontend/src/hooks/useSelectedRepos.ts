import { useCallback, useMemo, useState } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonArray, readJsonArray, removeKey } from "./storage";

const KEY = "better-gh.selected-repos";
const LEGACY_KEY = "better-gh.ignored-repos";

/**
 * The set of "owner/repo" strings the viewer wants this board to track.
 *
 * The selection is synced across the viewer's devices via the preference
 * store. Distinguishes "never set up" (key absent -> selected === null)
 * from "set up with an empty selection" (key present but []). A one-shot
 * soft migration consumes any legacy ignored-repos list so upgrading
 * users keep the same effective visibility instead of suddenly seeing the
 * "PICK YOUR REPOS" empty state. The legacy key stays device-local (not
 * synced) since it's consumed once and discarded.
 */
export function useSelectedRepos() {
  const rawSelected = useRawPref(KEY);
  const selected = useMemo(() => parseJsonArray(rawSelected), [rawSelected]);
  // Read the legacy ignore-list once; it's only consulted until migration.
  const [legacy, setLegacy] = useState<string[] | null>(() =>
    readJsonArray(LEGACY_KEY),
  );

  const selectedSet = useMemo(() => new Set(selected ?? []), [selected]);
  const legacySet = useMemo(() => new Set(legacy ?? []), [legacy]);
  const isInitialized = selected !== null;

  const persist = useCallback((next: string[]) => {
    setRaw(KEY, JSON.stringify(next));
  }, []);

  const toggle = useCallback(
    (repo: string, on: boolean) => {
      const set = new Set(selected ?? []);
      if (on) set.add(repo);
      else set.delete(repo);
      persist(Array.from(set));
    },
    [selected, persist],
  );

  const setAll = useCallback(
    (repos: string[]) => {
      persist(Array.from(new Set(repos)));
    },
    [persist],
  );

  const isSelectionEmpty = useCallback((): boolean => {
    if (isInitialized) return selectedSet.size === 0;
    // Mid-migration window: legacy data still drives visibility, so the
    // picker stays hidden until the /api/dashboard repos let us migrate.
    if (legacy !== null) return false;
    return true;
  }, [isInitialized, selectedSet, legacy]);

  const isVisible = useCallback(
    (repo: string): boolean => {
      if (isInitialized) return selectedSet.has(repo);
      if (legacy !== null) return !legacySet.has(repo);
      return false;
    },
    [isInitialized, selectedSet, legacy, legacySet],
  );

  const has = useCallback(
    (repo: string) => isInitialized && selectedSet.has(repo),
    [isInitialized, selectedSet],
  );

  /**
   * One-shot soft migration: map selected = (currently visible) \ ignored
   * from the list of repos the viewer actually has PRs in, then clear the
   * legacy key. No-op once already initialized or when no legacy exists.
   */
  const migrateFromRepos = useCallback(
    (repos: string[]) => {
      if (isInitialized || legacy === null) return;
      const keep = repos.filter((r) => !legacySet.has(r));
      persist(keep);
      removeKey(LEGACY_KEY);
      setLegacy(null);
    },
    [isInitialized, legacy, legacySet, persist],
  );

  return {
    isInitialized,
    isSelectionEmpty,
    isVisible,
    has,
    toggle,
    setAll,
    migrateFromRepos,
  };
}
