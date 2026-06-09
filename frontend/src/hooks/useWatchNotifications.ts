import { useEffect, useRef } from "react";

import type { Checks, Pr } from "../api/types";
import { watchKey } from "./useWatchedKeys";

/**
 * "All checks green" means there's at least one check and none of them are
 * pending or failed. A PR with no CI at all never counts as green, so we
 * don't spam a notification for repos that simply have no checks.
 */
export function checksAllGreen(checks: Checks): boolean {
  return checks.passed > 0 && checks.pending === 0 && checks.failed === 0;
}

export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

/**
 * Ask for notification permission. Safe to call repeatedly -- the browser
 * only prompts once and remembers the answer. Returns whether we're allowed
 * to show notifications afterwards.
 */
export async function ensureNotificationPermission(): Promise<boolean> {
  if (!notificationsSupported()) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    const result = await Notification.requestPermission();
    return result === "granted";
  } catch {
    return false;
  }
}

function notifyChecksGreen(pr: Pr): void {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  try {
    // `tag` collapses repeat notifications for the same PR; `renotify`
    // makes the OS re-alert even if a tagged one is still on screen.
    const notification = new Notification(`✅ Checks passed · #${pr.number}`, {
      body: `${pr.repo}\n${pr.title}`,
      tag: `better-gh:checks:${watchKey(pr.repo, pr.number)}`,
      renotify: true,
    } as NotificationOptions);
    notification.onclick = () => {
      window.focus();
      window.open(pr.url, "_blank", "noopener");
      notification.close();
    };
  } catch {
    /* notification construction can throw on some platforms -- ignore */
  }
}

/**
 * Watches the supplied PRs and fires a browser notification whenever a
 * *watched* PR transitions into the "all checks green" state. Notifications
 * surface even when the tab is inactive, which is the whole point -- but for
 * that to work the dashboard query must keep polling in the background while
 * anything is watched (see useDashboard's refetchIntervalInBackground).
 *
 * We seed each watched PR's last-known state on first sight so that checking
 * "Watch" on an already-green PR does *not* immediately notify; we only
 * notify on a not-green -> green edge.
 */
export function useWatchNotifications(
  prs: Pr[] | undefined,
  isWatched: (key: string) => boolean,
): void {
  // key -> was the PR green the last time we saw it
  const lastGreen = useRef<Map<string, boolean>>(new Map());

  useEffect(() => {
    if (!prs) return;

    const seen = new Set<string>();
    for (const pr of prs) {
      const key = watchKey(pr.repo, pr.number);
      if (!isWatched(key)) continue;
      seen.add(key);

      const green = checksAllGreen(pr.checks);
      const prev = lastGreen.current.get(key);

      // First time we see a watched PR: seed only, never notify.
      if (prev === undefined) {
        lastGreen.current.set(key, green);
        continue;
      }

      if (green && !prev) notifyChecksGreen(pr);
      lastGreen.current.set(key, green);
    }

    // Forget PRs that are no longer watched (or no longer present) so a
    // re-watch later starts fresh and re-seeds instead of double-firing.
    for (const key of lastGreen.current.keys()) {
      if (!seen.has(key)) lastGreen.current.delete(key);
    }
  }, [prs, isWatched]);
}
