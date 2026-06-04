import { useCallback, useState } from "react";

import { readString, writeString } from "./storage";

const KEY = "better-gh.active-tab";

export type TabName = "mine" | "reviews";

/**
 * Which dashboard tab is active (MY PRs / REVIEWING), persisted so a
 * reload keeps the viewer where they were.
 */
export function useActiveTab(): {
  tab: TabName;
  setTab: (name: TabName) => void;
} {
  const [tab, setTabState] = useState<TabName>(() =>
    readString(KEY) === "reviews" ? "reviews" : "mine",
  );

  const setTab = useCallback((name: TabName) => {
    setTabState(name);
    writeString(KEY, name);
  }, []);

  return { tab, setTab };
}
