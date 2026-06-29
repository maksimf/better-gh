import { useCallback, useMemo } from "react";

import { peekRaw, setRaw, useRawPref } from "./prefsStore";
import { parseJsonArray } from "./storage";

const KEY = "better-gh.reviewer-logins";
const LEGACY_KEY = "better-gh.reviewer-login";

/**
 * The viewer's tracked reviewer logins, synced across their devices.
 *
 * Stored as a JSON string array under ``better-gh.reviewer-logins``.
 * Distinguishes three states, mirroring the old single-reviewer hook:
 *
 *   null   -> unconfigured: the server falls back to REVIEWER_LOGIN.
 *   []     -> explicitly "track nobody": hide the chips entirely.
 *   [a,b]  -> track @a and @b's approvals.
 *
 * Transparent upgrade: when this key is unset we fall back to the legacy
 * single-login ``better-gh.reviewer-login`` value so an existing user
 * keeps tracking the same person without losing their setting. The first
 * explicit edit persists the array form. We deliberately leave the legacy
 * key in place so an older still-open tab keeps working.
 *
 * ``param`` is the comma-separated string sent to the API (see
 * ``useDashboard``) so the cached snapshot stays reviewer-agnostic and
 * shareable: null omits the param (use the default), "" sends the
 * explicit "nobody", "a,b" tracks those logins.
 */
function legacyReviewers(): string[] | null {
  const raw = peekRaw(LEGACY_KEY);
  if (raw === null) return null;
  const trimmed = raw.trim();
  return trimmed === "" ? [] : [trimmed];
}

export function useReviewers(): {
  reviewers: string[] | null;
  param: string | null;
  setReviewers: (next: string[]) => void;
  add: (login: string) => void;
  remove: (login: string) => void;
} {
  const raw = useRawPref(KEY);

  const reviewers = useMemo<string[] | null>(() => {
    const parsed = parseJsonArray(raw);
    if (parsed !== null) return parsed;
    return legacyReviewers();
  }, [raw]);

  const param = useMemo<string | null>(() => {
    if (reviewers === null) return null;
    return reviewers.join(",");
  }, [reviewers]);

  const setReviewers = useCallback((next: string[]) => {
    // Trim, drop blanks, and de-dupe case-insensitively while keeping the
    // first-seen spelling and the viewer's chosen order.
    const seen = new Set<string>();
    const cleaned: string[] = [];
    for (const login of next) {
      const value = login.trim();
      const key = value.toLowerCase();
      if (value && !seen.has(key)) {
        seen.add(key);
        cleaned.push(value);
      }
    }
    setRaw(KEY, JSON.stringify(cleaned));
  }, []);

  const add = useCallback(
    (login: string) => {
      setReviewers([...(reviewers ?? []), login]);
    },
    [reviewers, setReviewers],
  );

  const remove = useCallback(
    (login: string) => {
      const key = login.trim().toLowerCase();
      setReviewers((reviewers ?? []).filter((r) => r.toLowerCase() !== key));
    },
    [reviewers, setReviewers],
  );

  return { reviewers, param, setReviewers, add, remove };
}
