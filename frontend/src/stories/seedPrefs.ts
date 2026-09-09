import { hydrate, removeRaw, SYNCED_KEYS } from "../hooks/prefsStore";
import { writeString } from "../hooks/storage";
import type { TabName } from "../hooks/useActiveTab";

const TAB_KEY = "better-gh.active-tab";

/** Default viewer prefs for the full-app stories. */
export function appStoryPrefs(): Record<string, unknown> {
  return {
    "better-gh.selected-repos": ["acme/app", "acme/api"],
    "better-gh.deferred": ["acme/app#88", "acme/app#56"],
    "better-gh.manually-reviewed": ["acme/app#128"],
    "better-gh.watched": ["acme/app#101"],
    "better-gh.ntfy-channel": "better-gh-demo",
    "better-gh.pr-notes": {
      "acme/app#128": "Ship after the a11y pass.",
    },
    "better-gh.cloud-agents": {
      "acme/app#142": "agent_demo_1",
    },
    "better-gh.notes": "Standup: merge the stack if CI is green.",
  };
}

/**
 * Reset synced prefs, then fold in story values so App's first paint
 * matches the intended board (no empty-picker flash).
 */
export function seedAppStoryState(options?: {
  prefs?: Record<string, unknown>;
  tab?: TabName;
}): Record<string, unknown> {
  for (const key of SYNCED_KEYS) removeRaw(key);
  const prefs = { ...appStoryPrefs(), ...options?.prefs };
  hydrate(prefs);
  writeString(TAB_KEY, options?.tab ?? "mine");
  return prefs;
}
