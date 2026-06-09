import { useEffect, useRef } from "react";

import type { Pr } from "../api/types";
import { watchKey } from "./useWatchedKeys";

/**
 * A watched PR is "ready" -- and worth notifying about -- when:
 *   - at least one check passed and none are pending or failed, and
 *   - a preview deployment URL is available.
 * Requiring the preview means we only ping once the PR is actually clickable
 * to review, not the moment CI happens to go green.
 */
export function isReadyToNotify(pr: Pr): boolean {
  const { passed, pending, failed } = pr.checks;
  const checksGreen = passed > 0 && pending === 0 && failed === 0;
  return checksGreen && pr.preview_url != null;
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

function notifyReady(pr: Pr): void {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  try {
    // `tag` collapses repeat notifications for the same PR; `renotify`
    // makes the OS re-alert even if a tagged one is still on screen.
    const notification = new Notification(
      `✅ Ready · #${pr.number}`,
      {
        body: `${pr.repo}\n${pr.title}\nChecks passed · preview ready`,
        tag: `better-gh:ready:${watchKey(pr.repo, pr.number)}`,
        renotify: true,
      } as NotificationOptions,
    );
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
 * *watched* PR transitions into the "ready" state (see isReadyToNotify:
 * checks green AND preview available). Notifications surface even when the
 * tab is inactive, which is the whole point -- but for that to work the
 * dashboard query must keep polling in the background while anything is
 * watched (see useDashboard's refetchIntervalInBackground).
 *
 * We seed each watched PR's last-known state on first sight so that checking
 * "Watch" on an already-ready PR does *not* immediately notify; we only
 * notify on a not-ready -> ready edge.
 */
export function useWatchNotifications(
  prs: Pr[] | undefined,
  isWatched: (key: string) => boolean,
): void {
  // key -> was the PR "ready" the last time we saw it
  const lastReady = useRef<Map<string, boolean>>(new Map());

  useEffect(() => {
    if (!prs) return;

    const seen = new Set<string>();
    for (const pr of prs) {
      const key = watchKey(pr.repo, pr.number);
      if (!isWatched(key)) continue;
      seen.add(key);

      const ready = isReadyToNotify(pr);
      const prev = lastReady.current.get(key);

      // First time we see a watched PR: seed only, never notify.
      if (prev === undefined) {
        lastReady.current.set(key, ready);
        continue;
      }

      if (ready && !prev) notifyReady(pr);
      lastReady.current.set(key, ready);
    }

    // Forget PRs that are no longer watched (or no longer present) so a
    // re-watch later starts fresh and re-seeds instead of double-firing.
    for (const key of lastReady.current.keys()) {
      if (!seen.has(key)) lastReady.current.delete(key);
    }
  }, [prs, isWatched]);
}
