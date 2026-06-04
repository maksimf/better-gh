import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getJson, postJson } from "./client";
import type { Dashboard, Me } from "./types";

export const DASHBOARD_KEY = ["dashboard"] as const;

function dashboardUrl(reviewer: string | null): string {
  // reviewer === null  -> unconfigured: let the server use its default.
  // reviewer === ""    -> explicitly "no reviewer": send the empty param.
  if (reviewer === null) return "/api/dashboard";
  return `/api/dashboard?reviewer=${encodeURIComponent(reviewer)}`;
}

export function useDashboard(reviewer: string | null) {
  return useQuery({
    queryKey: [...DASHBOARD_KEY, reviewer],
    queryFn: () => getJson<Dashboard>(dashboardUrl(reviewer)),
    // Steady-state cadence while the tab is focused. The global client
    // defaults already disable background polling and enable refetch on
    // focus; this drives the interval from the server's POLL_INTERVAL.
    refetchInterval: (query) =>
      (query.state.data?.poll_interval_seconds ?? 300) * 1000,
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

export function useMergePr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ref: PrRef) => postJson(pullPath(ref, "merge")),
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
