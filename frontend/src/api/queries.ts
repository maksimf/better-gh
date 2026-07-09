import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getJson, postJson, putJson } from "./client";
import type {
  CloudAgentModel,
  CloudAgentStatus,
  Dashboard,
  DiffSide,
  GhUser,
  Me,
  PrComment,
  PrDiff,
  ReviewEvent,
} from "./types";

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

function dashboardUrl(reviewers: string | null): string {
  // reviewers === null -> unconfigured: let the server use its default.
  // reviewers === ""   -> explicitly "track nobody": send the empty param.
  // "a,b"              -> track those comma-separated logins.
  if (reviewers === null) return "/api/dashboard";
  return `/api/dashboard?reviewers=${encodeURIComponent(reviewers)}`;
}

export function useDashboard(reviewers: string | null) {
  return useQuery({
    queryKey: [...DASHBOARD_KEY, reviewers],
    queryFn: () => getJson<Dashboard>(dashboardUrl(reviewers)),
    refetchInterval: (query) =>
      (query.state.data?.poll_interval_seconds ?? 300) * 1000,
  });
}

/**
 * Debounced-friendly GitHub user search for the reviewer picker. The
 * caller is expected to pass an already-debounced query string; the query
 * is disabled (and never hits the network) for a blank term.
 */
export function useUserSearch(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["user-search", q],
    enabled: q.length > 0,
    queryFn: () =>
      getJson<GhUser[]>(`/api/users/search?q=${encodeURIComponent(q)}`),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

// How often to re-poll a cloud agent that's still running. Faster than
// the GitHub dashboard cadence since QA runs are short-lived; we stop
// entirely once the run reaches a terminal state.
const CLOUD_AGENT_POLL_MS = 15 * 1000;
const DEFAULT_QA_MODEL_ID = "composer-2.5";

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

export function useCloudAgentModels(enabled: boolean) {
  return useQuery({
    queryKey: ["cloud-agent-models"],
    queryFn: () =>
      getJson<{ items: CloudAgentModel[] }>("/api/cloud-agent/models").then(
        (res) => res.items,
      ),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export interface StartCloudAgentResult {
  id: string;
  url: string;
  name?: string | null;
}

export function useStartCloudAgent() {
  return useMutation({
    mutationFn: ({
      prompt,
      repo,
      modelId,
    }: {
      prompt: string;
      repo: string;
      modelId?: string | null;
    }) =>
      postJson<StartCloudAgentResult>("/api/cloud-agent", {
        prompt,
        repo,
        model_id: modelId ?? DEFAULT_QA_MODEL_ID,
      }),
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
      linearTicket = null,
    }: {
      ref: PrRef;
      markLinearDone?: boolean;
      linearTicket?: string | null;
    }) =>
      postJson<MergeResult>(pullPath(ref, "merge"), {
        mark_linear_done: markLinearDone,
        linear_ticket: linearTicket,
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
    mutationFn: ({
      ref,
      reviewers,
    }: {
      ref: PrRef;
      reviewers: string[];
    }) => postJson(pullPath(ref, "request-review"), { reviewers }),
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

export function usePrDiff(
  owner: string,
  repo: string,
  number: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["pr-diff", owner, repo, number],
    queryFn: () => getJson<PrDiff>(pullPath({ owner, repo, number }, "diff")),
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useApprovePr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, body }: { ref: PrRef; body?: string }) =>
      postJson(pullPath(ref, "review"), {
        event: "APPROVE",
        body: body ?? "",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export function useSubmitReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      ref,
      event,
      body,
    }: {
      ref: PrRef;
      event: ReviewEvent;
      body?: string;
    }) =>
      postJson(pullPath(ref, "review"), {
        event,
        body: body ?? "",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: DASHBOARD_KEY }),
  });
}

export function useAddPrComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, body }: { ref: PrRef; body: string }) =>
      postJson(pullPath(ref, "comment"), { body }),
    onSuccess: (_data, { ref }) => {
      qc.invalidateQueries({ queryKey: DASHBOARD_KEY });
      qc.invalidateQueries({
        queryKey: ["pr-comments", ref.owner, ref.repo, ref.number],
      });
    },
  });
}

export function useAddLineComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      ref,
      commitId,
      path,
      body,
      line,
      side,
      startLine,
      startSide,
    }: {
      ref: PrRef;
      commitId: string;
      path: string;
      body: string;
      line: number;
      side: DiffSide;
      startLine?: number;
      startSide?: DiffSide;
    }) =>
      postJson(pullPath(ref, "line-comment"), {
        commit_id: commitId,
        path,
        body,
        line,
        side,
        start_line: startLine ?? null,
        start_side: startSide ?? null,
      }),
    onSuccess: (_data, { ref }) => {
      qc.invalidateQueries({ queryKey: DASHBOARD_KEY });
      qc.invalidateQueries({
        queryKey: ["pr-diff", ref.owner, ref.repo, ref.number],
      });
      qc.invalidateQueries({
        queryKey: ["pr-comments", ref.owner, ref.repo, ref.number],
      });
    },
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
