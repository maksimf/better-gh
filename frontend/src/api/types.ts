// Shapes returned by the backend JSON API. These mirror
// `backend/app/serialize.py` -- keep them in sync.

export type Column = "progress" | "ready" | "approved";

export interface FailedCheck {
  name: string;
  url: string | null;
}

export interface Checks {
  passed: number;
  pending: number;
  failed: number;
  failed_names: FailedCheck[];
}

export interface StackNode {
  number: number;
  title: string;
  url: string;
  depth: number;
  column: Column;
  is_self: boolean;
}

/** Per-reviewer status for one tracked reviewer on a PR. */
export interface ReviewerStatus {
  login: string;
  approved: boolean;
  review_requested: boolean;
}

/** A GitHub user returned by the reviewer-search typeahead. */
export interface GhUser {
  login: string;
  avatar_url: string;
}

export interface Pr {
  number: number;
  title: string;
  url: string;
  repo: string;
  author: string;
  is_draft: boolean;
  is_ready: boolean;
  checks: Checks;
  comments_human: number;
  comments_bot: number;
  preview_url: string | null;
  conflicts: number;
  additions: number;
  deletions: number;
  linear_url: string | null;
  updated_at: string;
  column: Column;
  approved: boolean;
  review_requested: boolean;
  reviewers: ReviewerStatus[];
  stack_id: string | null;
  stack_order: number | null;
  stack_depth: number | null;
  stack_co_column: boolean;
  stack_nodes: StackNode[];
}

export interface ReviewPr {
  number: number;
  title: string;
  url: string;
  repo: string;
  author: string;
  is_draft: boolean;
  checks: Checks;
  conflicts: number;
  additions: number;
  deletions: number;
  updated_at: string;
  requested_at: string;
}

export interface RepoSummary {
  repo: string;
  count: number;
}

export interface DashboardError {
  message: string;
  reset_at: string | null;
}

export interface Dashboard {
  prs: Pr[];
  reviews: ReviewPr[];
  repos: RepoSummary[];
  reviewers: string[];
  last_polled_at: string | null;
  error: DashboardError | null;
  poll_interval_seconds: number;
}

export interface Me {
  login: string;
  avatar_url: string;
}

export interface PrComment {
  id: number;
  type: "review" | "issue";
  author: string;
  body: string;
  url: string;
}

export type DiffFileStatus =
  | "added"
  | "removed"
  | "modified"
  | "renamed"
  | "copied"
  | "changed"
  | "unchanged";

export interface DiffFile {
  filename: string;
  status: DiffFileStatus | string;
  additions: number;
  deletions: number;
  patch: string | null;
  previous_filename: string | null;
}

export interface PrDiff {
  body: string | null;
  files: DiffFile[];
}

export type CloudAgentState = "running" | "done" | "error" | "unknown";

export interface CloudAgentStatus {
  configured: boolean;
  state: CloudAgentState;
  status: string | null;
  url?: string | null;
  pr_url?: string | null;
  name?: string | null;
  video_path?: string | null;
  error?: string | null;
}

export interface CloudAgentModel {
  id: string;
  displayName: string;
  description?: string | null;
}
