import { useCallback, useState } from "react";

import { readString, removeKey, writeString } from "./storage";

const KEY = "better-gh.ntfy-channel";

/**
 * The ntfy.sh topic/channel watched-PR notifications are published to,
 * persisted in localStorage.
 *
 *   null / "" -> unconfigured: watching is disabled until a channel is set.
 *   "my-prs"  -> POST ready notifications to https://ntfy.sh/my-prs.
 *
 * Pure client-side; the server never sees it.
 */
export function useNtfyChannel(): {
  channel: string;
  setChannel: (value: string) => void;
} {
  const [channel, setChannelState] = useState<string>(
    () => readString(KEY) ?? "",
  );

  const setChannel = useCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed === "") {
      removeKey(KEY);
      setChannelState("");
      return;
    }
    writeString(KEY, trimmed);
    setChannelState(trimmed);
  }, []);

  return { channel, setChannel };
}
