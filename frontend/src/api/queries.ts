import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getJson, postJson } from "./client";
import type { Dashboard, Me } from "./types";

export const DASHBOARD_KEY = ["dashboard"] as const;

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

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => getJson<Me>("/me"),
    staleTime: Infinity,
    refetchInterval: false,
  });
}

interface PrRef {
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
