import { http, HttpResponse, delay } from "msw";

import {
  dashboardFixture,
  meFixture,
  prComments,
  prDiff,
} from "../fixtures";

export const handlers = [
  http.get("/me", () => HttpResponse.json(meFixture)),

  http.get("/api/prefs", () =>
    HttpResponse.json({
      ntfy_channel: "better-gh-demo",
      reviewers: ["alice", "bob"],
    }),
  ),

  http.put("/api/prefs", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(body);
  }),

  http.get("/api/dashboard", () => HttpResponse.json(dashboardFixture)),

  http.get("/api/users/search", ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const users = [
      { login: "alice", avatar_url: "https://avatars.githubusercontent.com/u/2?v=4" },
      { login: "bob", avatar_url: "https://avatars.githubusercontent.com/u/3?v=4" },
      { login: "carol", avatar_url: "https://avatars.githubusercontent.com/u/4?v=4" },
    ].filter((u) => u.login.includes(q));
    return HttpResponse.json(users);
  }),

  http.get("/pulls/:owner/:repo/:number/comments", () =>
    HttpResponse.json(prComments),
  ),

  http.get("/pulls/:owner/:repo/:number/diff", async () => {
    await delay(200);
    return HttpResponse.json(prDiff);
  }),

  http.post("/pulls/:owner/:repo/:number/merge", async () => {
    await delay(300);
    return HttpResponse.json({
      merged: true,
      linear_done: false,
      linear_error: null,
    });
  }),

  http.post("/pulls/bulk-merge", async () => {
    await delay(300);
    return HttpResponse.json({ results: [] });
  }),

  http.post("/pulls/:owner/:repo/:number/review", async () => {
    await delay(300);
    return HttpResponse.json({ approved: true });
  }),

  http.post("/pulls/:owner/:repo/:number/ready-for-review", async () => {
    await delay(200);
    return HttpResponse.json({ draft: false });
  }),

  http.post("/pulls/:owner/:repo/:number/request-review", async () => {
    await delay(200);
    return HttpResponse.json({ requested: true });
  }),

  http.post("/pulls/:owner/:repo/:number/comment", async () => {
    await delay(200);
    return HttpResponse.json({ ok: true });
  }),

  http.post("/pulls/:owner/:repo/:number/line-comment", async () => {
    await delay(200);
    return HttpResponse.json({ ok: true });
  }),

  http.post("/pulls/:owner/:repo/:number/ack-comment", () =>
    HttpResponse.json({ ok: true }),
  ),

  http.post("/pulls/:owner/:repo/:number/reply-comment", () =>
    HttpResponse.json({ ok: true }),
  ),

  http.post("/api/cloud-agent", async () => {
    await delay(400);
    return HttpResponse.json({
      id: "agent_demo_1",
      url: "https://cursor.com/agents/agent_demo_1",
      name: "QA demo agent",
    });
  }),

  http.get("/api/cloud-agent/models", () =>
    HttpResponse.json({
      items: [
        {
          id: "composer-2.5",
          displayName: "Composer 2.5",
          description: "Fast coding agent",
        },
        {
          id: "claude-opus-5-thinking-high",
          displayName: "Claude Opus",
          description: "Deep reasoning",
        },
      ],
    }),
  ),

  http.get("/api/cloud-agent/:id", ({ params }) =>
    HttpResponse.json({
      configured: true,
      state: "done",
      status: "Finished",
      url: `https://cursor.com/agents/${params.id}`,
      pr_url: "https://github.com/acme/app/pull/128",
      name: "QA demo agent",
      video_path: "recordings/demo.mp4",
      error: null,
    }),
  ),

  http.get("/api/cloud-agent/:id/video-url", () =>
    HttpResponse.json({
      url: "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
      expires_at: "2099-01-01T00:00:00Z",
    }),
  ),

  http.post("/refresh", () => HttpResponse.json({ ok: true })),
];

/** Force mutation endpoints to fail for error-state stories. */
export const failingMutationHandlers = [
  http.post("/pulls/:owner/:repo/:number/merge", () =>
    HttpResponse.json({ detail: "Merge conflict" }, { status: 409 }),
  ),
  http.post("/pulls/:owner/:repo/:number/review", () =>
    HttpResponse.json({ detail: "Already reviewed" }, { status: 422 }),
  ),
  http.post("/pulls/:owner/:repo/:number/ready-for-review", () =>
    HttpResponse.json({ detail: "Not a draft" }, { status: 400 }),
  ),
];
