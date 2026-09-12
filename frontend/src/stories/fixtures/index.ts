import type {
  Checks,
  Dashboard,
  Me,
  Pr,
  PrComment,
  PrDiff,
  ReviewPr,
  ReviewerStatus,
  RepoSummary,
  StackNode,
} from "../../api/types";

export const meFixture: Me = {
  login: "maxfilippov",
  avatar_url: "https://avatars.githubusercontent.com/u/1?v=4",
};

export const checksPass: Checks = {
  passed: 12,
  pending: 0,
  failed: 0,
  failed_names: [],
};

export const checksPending: Checks = {
  passed: 8,
  pending: 3,
  failed: 0,
  failed_names: [],
};

export const checksFail: Checks = {
  passed: 9,
  pending: 0,
  failed: 2,
  failed_names: [
    { name: "ci / test", url: "https://github.com/acme/app/actions/runs/1" },
    { name: "lint", url: "https://github.com/acme/app/actions/runs/2" },
  ],
};

export const checksZero: Checks = {
  passed: 0,
  pending: 0,
  failed: 0,
  failed_names: [],
};

export const reviewersApproved: ReviewerStatus[] = [
  { login: "alice", approved: true, review_requested: true },
  { login: "bob", approved: true, review_requested: true },
];

export const reviewersMixed: ReviewerStatus[] = [
  { login: "alice", approved: true, review_requested: true },
  { login: "bob", approved: false, review_requested: true },
  { login: "carol", approved: false, review_requested: false },
];

export const reviewersPending: ReviewerStatus[] = [
  { login: "alice", approved: false, review_requested: false },
  { login: "bob", approved: false, review_requested: false },
];

function basePr(overrides: Partial<Pr> = {}): Pr {
  return {
    number: 128,
    title: "Add Storybook catalog for dashboard UI",
    url: "https://github.com/acme/app/pull/128",
    repo: "acme/app",
    author: "maxfilippov",
    is_draft: false,
    is_ready: true,
    checks: checksPass,
    comments_human: 3,
    comments_bot: 2,
    preview_url: "https://preview.example.com/pr-128",
    conflicts: 0,
    additions: 240,
    deletions: 48,
    linear_url: "https://linear.app/acme/issue/ENG-128",
    video_url: null,
    updated_at: "2026-08-12T12:00:00Z",
    column: "ready",
    approved: false,
    review_requested: true,
    reviewers: reviewersMixed,
    stack_id: null,
    stack_order: null,
    stack_depth: null,
    stack_co_column: false,
    stack_nodes: [],
    ...overrides,
  };
}

export const prReady = basePr();

export const prDraft = basePr({
  number: 101,
  title: "WIP: redesign empty states",
  is_draft: true,
  is_ready: false,
  column: "progress",
  checks: checksPending,
  comments_human: 0,
  comments_bot: 1,
  preview_url: null,
  linear_url: null,
  reviewers: reviewersPending,
});

export const prApproved = basePr({
  number: 142,
  title: "Ship merge modal Linear shortcut",
  column: "approved",
  approved: true,
  is_ready: true,
  checks: checksPass,
  reviewers: reviewersApproved,
});

export const prFailing = basePr({
  number: 99,
  title: "Fix flaky CI on main",
  column: "progress",
  is_ready: false,
  checks: checksFail,
  conflicts: 2,
  preview_url: null,
});

const stack1Nodes = (self: number): StackNode[] => [
  {
    number: 129,
    title: "Stacked: extract Button primitive",
    url: "https://github.com/acme/app/pull/129",
    depth: 0,
    column: "approved",
    is_self: self === 129,
  },
  {
    number: 130,
    title: "Stacked: extract Dialog primitive",
    url: "https://github.com/acme/app/pull/130",
    depth: 1,
    column: "ready",
    is_self: self === 130,
  },
  {
    number: 131,
    title: "Stacked: add Storybook stories",
    url: "https://github.com/acme/app/pull/131",
    depth: 2,
    column: "progress",
    is_self: self === 131,
  },
];

export const prStackRoot = basePr({
  number: 129,
  title: "Stacked: extract Button primitive",
  column: "approved",
  approved: true,
  is_ready: true,
  reviewers: reviewersApproved,
  stack_id: "stack-1",
  stack_order: 0,
  stack_depth: 0,
  stack_co_column: false,
  stack_nodes: stack1Nodes(129),
});

export const prStacked = basePr({
  number: 130,
  title: "Stacked: extract Dialog primitive",
  column: "ready",
  stack_id: "stack-1",
  stack_order: 1,
  stack_depth: 1,
  stack_co_column: false,
  stack_nodes: stack1Nodes(130),
});

export const prStackLeaf = basePr({
  number: 131,
  title: "Stacked: add Storybook stories",
  column: "progress",
  is_ready: false,
  checks: checksPending,
  reviewers: reviewersPending,
  stack_id: "stack-1",
  stack_order: 2,
  stack_depth: 2,
  stack_co_column: false,
  stack_nodes: stack1Nodes(131),
});

export const prExternal = basePr({
  number: 77,
  title: "Docs: clarify reviewer picker",
  author: "alice",
  url: "https://github.com/acme/app/pull/77",
  column: "ready",
  reviewers: reviewersPending,
});

export const prNoChecks = basePr({
  number: 90,
  title: "Just opened — checks have not started",
  url: "https://github.com/acme/app/pull/90",
  column: "progress",
  is_ready: false,
  checks: checksZero,
  preview_url: null,
  linear_url: null,
  comments_human: 0,
  comments_bot: 0,
  additions: 18,
  deletions: 2,
  reviewers: [],
  review_requested: false,
});

export const prConflicts = basePr({
  number: 104,
  title: "Rebase onto main — 4 conflicts",
  url: "https://github.com/acme/app/pull/104",
  column: "progress",
  is_ready: false,
  checks: checksPass,
  conflicts: 4,
  preview_url: null,
  comments_human: 1,
  comments_bot: 0,
});

export const prAwaitingReview = basePr({
  number: 110,
  title: "Ready: waiting on first review",
  url: "https://github.com/acme/app/pull/110",
  column: "ready",
  review_requested: false,
  reviewers: reviewersPending,
  comments_human: 0,
  comments_bot: 0,
  additions: 96,
  deletions: 14,
});

export const prBusyThread = basePr({
  number: 133,
  title: "Hot discussion on the settings modal",
  url: "https://github.com/acme/app/pull/133",
  column: "ready",
  comments_human: 18,
  comments_bot: 7,
  additions: 820,
  deletions: 340,
});

export const prOtherRepo = basePr({
  number: 12,
  title: "API: paginate dashboard snapshot",
  url: "https://github.com/acme/api/pull/12",
  repo: "acme/api",
  column: "ready",
  linear_url: "https://linear.app/acme/issue/API-12",
  preview_url: null,
  additions: 64,
  deletions: 21,
});

export const prParked = basePr({
  number: 88,
  title: "Parked: rewrite preview cache later",
  url: "https://github.com/acme/app/pull/88",
  column: "ready",
  comments_human: 2,
  comments_bot: 0,
  preview_url: null,
});

export const prApprovedWithVideo = basePr({
  number: 150,
  title: "Approved: includes QA walkthrough video",
  url: "https://github.com/acme/app/pull/150",
  column: "approved",
  approved: true,
  is_ready: true,
  reviewers: reviewersApproved,
  video_url:
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
  additions: 310,
  deletions: 22,
});

export const reviewPr: ReviewPr = {
  number: 55,
  title: "Review: tighten rate-limit banner",
  url: "https://github.com/acme/app/pull/55",
  repo: "acme/app",
  author: "bob",
  is_draft: false,
  checks: checksPass,
  conflicts: 0,
  additions: 40,
  deletions: 12,
  updated_at: "2026-08-12T10:00:00Z",
  requested_at: "2026-08-11T18:00:00Z",
  stack_id: null,
  stack_order: null,
  stack_depth: null,
  stack_co_column: false,
  stack_nodes: [],
};

const reviewStackNodes = (self: number): StackNode[] => [
  {
    number: 70,
    title: "Review stack: auth foundation",
    url: "https://github.com/acme/app/pull/70",
    depth: 0,
    column: "progress",
    is_self: self === 70,
  },
  {
    number: 71,
    title: "Review stack: session store",
    url: "https://github.com/acme/app/pull/71",
    depth: 1,
    column: "progress",
    is_self: self === 71,
  },
  {
    number: 72,
    title: "Review stack: login UI",
    url: "https://github.com/acme/app/pull/72",
    depth: 2,
    column: "progress",
    is_self: self === 72,
  },
];

export const reviewStackRoot: ReviewPr = {
  ...reviewPr,
  number: 70,
  title: "Review stack: auth foundation",
  url: "https://github.com/acme/app/pull/70",
  requested_at: "2026-08-12T09:00:00Z",
  stack_id: "acme/app#70",
  stack_order: 0,
  stack_depth: 0,
  stack_co_column: true,
  stack_nodes: reviewStackNodes(70),
};

export const reviewStacked: ReviewPr = {
  ...reviewPr,
  number: 71,
  title: "Review stack: session store",
  url: "https://github.com/acme/app/pull/71",
  requested_at: "2026-08-12T09:10:00Z",
  stack_id: "acme/app#70",
  stack_order: 1,
  stack_depth: 1,
  stack_co_column: true,
  stack_nodes: reviewStackNodes(71),
};

export const reviewStackLeaf: ReviewPr = {
  ...reviewPr,
  number: 72,
  title: "Review stack: login UI",
  url: "https://github.com/acme/app/pull/72",
  requested_at: "2026-08-12T09:20:00Z",
  stack_id: "acme/app#70",
  stack_order: 2,
  stack_depth: 2,
  stack_co_column: true,
  stack_nodes: reviewStackNodes(72),
};

export const reviewPrDraft: ReviewPr = {
  ...reviewPr,
  number: 56,
  title: "Draft review request",
  url: "https://github.com/acme/app/pull/56",
  is_draft: true,
  checks: checksPending,
};

export const reviewPrFailing: ReviewPr = {
  ...reviewPr,
  number: 61,
  title: "Review: CI is red on the webhook path",
  url: "https://github.com/acme/app/pull/61",
  checks: checksFail,
  conflicts: 1,
  additions: 210,
  deletions: 40,
  requested_at: "2026-08-12T08:30:00Z",
};

export const reviewPrOtherRepo: ReviewPr = {
  ...reviewPr,
  number: 9,
  title: "Review: tighten auth cookie flags",
  url: "https://github.com/acme/api/pull/9",
  repo: "acme/api",
  author: "carol",
  requested_at: "2026-08-10T09:00:00Z",
};

export const repoSummaries: RepoSummary[] = [
  { repo: "acme/app", count: 17 },
  { repo: "acme/api", count: 2 },
  { repo: "acme/docs", count: 0 },
];

export const dashboardFixture: Dashboard = {
  prs: [
    prDraft,
    prNoChecks,
    prFailing,
    prConflicts,
    prReady,
    prAwaitingReview,
    prBusyThread,
    prExternal,
    prOtherRepo,
    prParked,
    prApproved,
    prApprovedWithVideo,
    prStackRoot,
    prStacked,
    prStackLeaf,
  ],
  reviews: [
    reviewPr,
    reviewPrDraft,
    reviewPrFailing,
    reviewPrOtherRepo,
    reviewStackRoot,
    reviewStacked,
    reviewStackLeaf,
  ],
  repos: repoSummaries,
  reviewers: ["alice", "bob"],
  last_polled_at: "2026-08-12T12:05:00Z",
  error: null,
  poll_interval_seconds: 300,
};

export const dashboardEmptyFixture: Dashboard = {
  ...dashboardFixture,
  prs: [],
  reviews: [],
  repos: [
    { repo: "acme/app", count: 0 },
    { repo: "acme/api", count: 0 },
    { repo: "acme/docs", count: 0 },
  ],
};

export const dashboardRateLimitedFixture: Dashboard = {
  ...dashboardFixture,
  error: {
    message: "GitHub rate limit exceeded",
    reset_at: "2026-08-12T13:00:00Z",
  },
};

export const prComments: PrComment[] = [
  {
    id: 1,
    type: "review",
    author: "alice",
    body: "Looks good — one nit on the Dialog props.",
    url: "https://github.com/acme/app/pull/128#discussion_r1",
  },
  {
    id: 2,
    type: "issue",
    author: "bob",
    body: "Can we cover the dark theme in Storybook too?",
    url: "https://github.com/acme/app/pull/128#issuecomment-2",
  },
];

export const prDiff: PrDiff = {
  body: "Adds Storybook catalog and extracts shared UI primitives.",
  head_sha: "abc123def456",
  files: [
    {
      filename: "frontend/src/ui/Dialog.tsx",
      status: "added",
      additions: 48,
      deletions: 0,
      patch:
        "@@ -0,0 +1,48 @@\n+export function Dialog() {\n+  return null;\n+}",
      previous_filename: null,
    },
    {
      filename: "frontend/src/components/PrCard.tsx",
      status: "modified",
      additions: 12,
      deletions: 8,
      patch:
        "@@ -180,7 +180,7 @@\n-          {pr.is_draft && <span className=\"pr-tag pr-tag--draft\">Draft</span>}\n+          {pr.is_draft && <Tag variant=\"draft\">Draft</Tag>}",
      previous_filename: null,
    },
  ],
};
