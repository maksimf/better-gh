import { useCallback, useState } from "react";

import { readString, removeKey, writeString } from "./storage";

const KEY = "better-gh.reviewer-login";

/**
 * The viewer's tracked reviewer login, persisted in localStorage.
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
  const [reviewer, setReviewerState] = useState<string | null>(() =>
    readString(KEY),
  );

  const setReviewer = useCallback((value: string | null) => {
    if (value === null) {
      removeKey(KEY);
      setReviewerState(null);
      return;
    }
    const trimmed = value.trim();
    writeString(KEY, trimmed);
    setReviewerState(trimmed);
  }, []);

  return { reviewer, setReviewer };
}
