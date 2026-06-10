import { useCallback } from "react";

import { removeRaw, setRaw, useRawPref } from "./prefsStore";

const KEY = "better-gh.ntfy-channel";

/**
 * The ntfy.sh topic/channel watched-PR notifications are published to,
 * synced across the viewer's devices.
 *
 *   null / "" -> unconfigured: watching is disabled until a channel is set.
 *   "my-prs"  -> POST ready notifications to https://ntfy.sh/my-prs.
 */
export function useNtfyChannel(): {
  channel: string;
  setChannel: (value: string) => void;
} {
  const raw = useRawPref(KEY);
  const channel = raw ?? "";

  const setChannel = useCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed === "") {
      removeRaw(KEY);
      return;
    }
    setRaw(KEY, trimmed);
  }, []);

  return { channel, setChannel };
}
