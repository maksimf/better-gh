import { useCallback, useMemo } from "react";

import { setRaw, useRawPref } from "./prefsStore";
import { parseJsonRecord } from "./storage";

const KEY = "better-gh.cloud-agents";

/**
 * Per-PR links to a Cursor cloud agent QAing the PR, keyed by
 * "owner/repo#number" -> agent id (e.g. "bc-95ed48f0-..."). Synced across
 * the viewer's devices via the preference store; the server also sees the
 * agent id when the card polls /api/cloud-agent/{id} for state.
 */
export function useCloudAgents() {
  const raw = useRawPref(KEY);
  const map = useMemo(() => parseJsonRecord(raw) ?? {}, [raw]);

  const get = useCallback((key: string): string | null => map[key] ?? null, [map]);

  const set = useCallback(
    (key: string, agentId: string) => {
      setRaw(KEY, JSON.stringify({ ...map, [key]: agentId }));
    },
    [map],
  );

  const remove = useCallback(
    (key: string) => {
      if (!(key in map)) return;
      const next = { ...map };
      delete next[key];
      setRaw(KEY, JSON.stringify(next));
    },
    [map],
  );

  return { get, set, remove };
}

export function cloudAgentKey(repo: string, number: number): string {
  return `${repo}#${number}`;
}

/**
 * Pull the cloud-agent id out of whatever the user pasted. Accepts a full
 * run URL (https://cursor.com/agents/bc-..., the v0 ?id=bc_... form, or a
 * bare id). Returns null when nothing that looks like an agent id is
 * found. Agent ids are "bc" + "-"/"_" + alphanumerics/hyphens.
 */
export function parseCursorAgentId(input: string): string | null {
  if (!input) return null;
  const match = input.trim().match(/bc[-_][A-Za-z0-9-]+/);
  if (!match) return null;
  // Trim any trailing hyphen the greedy charset might have grabbed.
  return match[0].replace(/-+$/, "");
}

export function cursorAgentUrl(agentId: string): string {
  return `https://cursor.com/agents/${agentId}`;
}
