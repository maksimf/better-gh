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

/**
 * Publish a "ready" notification to the configured ntfy.sh channel. ntfy
 * delivers it to every device subscribed to that topic, so alerts work even
 * when this tab is closed. Header values must be ISO-8859-1, so the title
 * stays plain text and the checkmark is supplied via the Tags emoji shortcode.
 */
async function notifyReady(pr: Pr, channel: string): Promise<void> {
  try {
    await fetch(`https://ntfy.sh/${encodeURIComponent(channel)}`, {
      method: "POST",
      body: `${pr.repo}\n${pr.title}\nChecks passed \u00B7 preview ready`,
      headers: {
        Title: `Ready - #${pr.number}`,
        Click: pr.url,
        Tags: "white_check_mark",
      },
    });
  } catch {
    /* network errors -- ignore, we'll try again on the next ready edge */
  }
}

/**
 * Watches the supplied PRs and publishes an ntfy.sh notification whenever a
 * *watched* PR transitions into the "ready" state (see isReadyToNotify:
 * checks green AND preview available). Because ntfy fans out to subscribed
 * devices, alerts surface even when the tab is inactive -- but for that to
 * work the dashboard query must keep polling in the background while anything
 * is watched (see useDashboard's refetchIntervalInBackground).
 *
 * Notifications are skipped entirely when no `channel` is configured.
 *
 * We seed each watched PR's last-known state on first sight so that checking
 * "Watch" on an already-ready PR does *not* immediately notify; we only
 * notify on a not-ready -> ready edge.
 */
export function useWatchNotifications(
  prs: Pr[] | undefined,
  isWatched: (key: string) => boolean,
  channel: string,
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

      if (ready && !prev && channel) void notifyReady(pr, channel);
      lastReady.current.set(key, ready);
    }

    // Forget PRs that are no longer watched (or no longer present) so a
    // re-watch later starts fresh and re-seeds instead of double-firing.
    for (const key of lastReady.current.keys()) {
      if (!seen.has(key)) lastReady.current.delete(key);
    }
  }, [prs, isWatched, channel]);
}
