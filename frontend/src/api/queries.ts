import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getJson, postJson, putJson } from "./client";
import type { CloudAgentStatus, Dashboard, Me, PrComment } from "./types";

export const DASHBOARD_KEY = ["dashboard"] as const;
export const PREFS_KEY = ["prefs"] as const;

/** The viewer's synced preferences: a flat ``{ key: value }`` map. */
export type Prefs = Record<string, unknown>;

export function getPrefs(): Promise<Prefs> {
  return getJson<Prefs>("/api/prefs");
}

export function putPrefs(body: Record<string, unknown>): Promise<Prefs | null> {
  return putJson<Prefs>("/api/prefs", body);
}

/**
 * Pull the viewer's server-side preferences. Rides the global
 * refetchOnWindowFocus default so another device's changes land when the
 * user returns to the tab; refetched on the same cadence as the dashboard
 * so cross-device sync settles within one poll cycle.
 */
export function usePrefs() {
  return useQuery({
    queryKey: PREFS_KEY,
    queryFn: getPrefs,
    staleTime: 30_000,
    refetchInterval: 5 * 60 * 1000,
  });
}

// While the tab is hidden we only poll to drive Watch notifications, so we
// deliberately throttle to a slow cadence to stay well clear of GitHub's
// rate limit. Foreground polling keeps the server-driven interval.
const BACKGROUND_POLL_MS = 10 * 60 * 1000;

function dashboardUrl(reviewer: string | null): string {
  // reviewer === null  -> unconfigured: let the server use its default.
  // reviewer === ""    -> explicitly "no reviewer": send the empty param.
  if (reviewer === null) return "/api/dashboard";
  return `/api/dashboard?reviewer=${encodeURIComponent(reviewer)}`;
}

export function useDashboard(
  reviewer: string | null,
  watchInBackground = false,
) {
  return useQuery({
    queryKey: [...DASHBOARD_KEY, reviewer],
    queryFn: () => getJson<Dashboard>(dashboardUrl(reviewer)),
    // Steady-state cadence: the server's POLL_INTERVAL while focused, but
    // throttled to BACKGROUND_POLL_MS while the tab is hidden so Watch
    // polling doesn't burn through GitHub's rate limit. react-query re-reads
    // this after each fetch, so the cadence settles within one cycle of a
    // visibility change.
    refetchInterval: (query) => {
      const base = (query.state.data?.poll_interval_seconds ?? 300) * 1000;
      const hidden = typeof document !== "undefined" && document.hidden;
      return hidden ? Math.max(base, BACKGROUND_POLL_MS) : base;
    },
    // When the user is watching at least one PR we keep polling even while
    // the tab is hidden, so the "checks went green" browser notification can
    // fire without the tab being focused. Otherwise a backgrounded tab stops
    // hitting the API entirely (the global default).
    refetchIntervalInBackground: watchInBackground,
  });
}

// How often to re-poll a cloud agent that's still running. Faster than
// the GitHub dashboard cadence since QA runs are short-lived; we stop
// entirely once the run reaches a terminal state.
const CLOUD_AGENT_POLL_MS = 15 * 1000;

export function useCloudAgentStatus(agentId: string | null) {
  return useQuery({
    queryKey: ["cloud-agent", agentId],
    enabled: agentId !== null,
    queryFn: () =>
      getJson<CloudAgentStatus>(
        `/api/cloud-agent/${encodeURIComponent(agentId as string)}`,
      ),
    // Keep polling while the run is in flight (or its state is still
    // indeterminate); once it's done/errored/unconfigured there's nothing
    // left to watch, so go quiet.
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "running" || state === "unknown"
        ? CLOUD_AGENT_POLL_MS
        : false;
    },
    staleTime: 5_000,
  });
}

export interface StartCloudAgentResult {
  id: string;
  url: string;
  name?: string | null;
}

export function useStartCloudAgent() {
  return useMutation({
    mutationFn: ({ prompt, repo }: { prompt: string; repo: string }) =>
      postJson<StartCloudAgentResult>("/api/cloud-agent", { prompt, repo }),
  });
}

export interface CloudAgentVideo {
  url: string | null;
  expires_at?: string | null;
}

export function useCloudAgentVideo(
  agentId: string | null,
  path: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["cloud-agent-video", agentId, path],
    enabled: enabled && agentId !== null && path !== null,
    queryFn: () =>
      getJson<CloudAgentVideo>(
        `/api/cloud-agent/${encodeURIComponent(
          agentId as string,
        )}/video-url?path=${encodeURIComponent(path as string)}`,
      ),
    // Presigned URLs live ~15 min; cache for 10 and don't auto-refetch.
    staleTime: 10 * 60 * 1000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => getJson<Me>("/me"),
    staleTime: Infinity,
    refetchInterval: false,
  });
}

export interface PrRef {
  owner: string;
  repo: string;
  number: number;
}

function pullPath({ owner, repo, number }: PrRef, action: string): string {
  return `/pulls/${encodeURIComponent(owner)}/${encodeURIComponent(
    repo,
  )}/${encodeURIComponent(String(number))}/${action}`;
}

export function useRefresh() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => postJson("/refresh"),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export interface MergeResult {
  merged: boolean;
  linear_done: boolean;
  linear_error: string | null;
}

export function useMergePr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      ref,
      markLinearDone = false,
    }: {
      ref: PrRef;
      markLinearDone?: boolean;
    }) =>
      postJson<MergeResult>(pullPath(ref, "merge"), {
        mark_linear_done: markLinearDone,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export function useMarkReady() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ref: PrRef) => postJson(pullPath(ref, "ready-for-review")),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export function useRequestReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, reviewer }: { ref: PrRef; reviewer: string | null }) =>
      postJson(pullPath(ref, "request-review"), { reviewer }),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export function usePrComments(
  owner: string,
  repo: string,
  number: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["pr-comments", owner, repo, number],
    queryFn: () =>
      getJson<PrComment[]>(
        `/pulls/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${encodeURIComponent(String(number))}/comments`,
      ),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useAckComment() {
  return useMutation({
    mutationFn: ({
      ref,
      commentId,
      commentType,
    }: {
      ref: PrRef;
      commentId: number;
      commentType: string;
    }) =>
      postJson(pullPath(ref, "ack-comment"), {
        comment_id: commentId,
        comment_type: commentType,
      }),
  });
}

export function useReplyComment() {
  return useMutation({
    mutationFn: ({
      ref,
      quotedAuthor,
      quotedBody,
      reply,
    }: {
      ref: PrRef;
      quotedAuthor: string;
      quotedBody: string;
      reply: string;
    }) =>
      postJson(pullPath(ref, "reply-comment"), {
        quoted_author: quotedAuthor,
        quoted_body: quotedBody,
        reply,
      }),
  });
}
