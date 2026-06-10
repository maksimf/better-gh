import { useCallback } from "react";

import { removeRaw, setRaw, useRawPref } from "./prefsStore";

const KEY = "better-gh.reviewer-login";

/**
 * The viewer's tracked reviewer login, synced across their devices.
 *
 *   null  -> unconfigured: the server falls back to REVIEWER_LOGIN.
 *   ""    -> explicitly "no reviewer": hide the chip entirely.
 *   "foo" -> track @foo's approvals.
 *
 * The value is sent to the API as a query param (see useDashboard) so
 * the cached snapshot stays reviewer-agnostic and shareable.
 */
export function useReviewer(): {
  reviewer: string | null;
  setReviewer: (value: string | null) => void;
} {
  const reviewer = useRawPref(KEY);

  const setReviewer = useCallback((value: string | null) => {
    if (value === null) {
      removeRaw(KEY);
      return;
    }
    setRaw(KEY, value.trim());
  }, []);

  return { reviewer, setReviewer };
}
