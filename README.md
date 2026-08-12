# Better GitHub UI

A clearer, calmer view of your open pull requests. Bauhaus-styled, a
React + react-query single-page app backed by a tiny FastAPI service
that polls GitHub and serves the snapshot as JSON.

react-query drives the live updates: it polls the dashboard while the
tab is focused, stops entirely when the tab is hidden, and refetches the
moment you switch back to it.

Anyone with a GitHub account can sign in via OAuth. The runtime stays
database-free: each viewer's access token rides on a signed HttpOnly
cookie, and their PR snapshot lives only in process memory for as long
as they keep fetching (an idle reaper cancels the per-user poller once
they stop).

The one bit of durable state is per-user **preferences** — the settings
that used to live only in the browser's `localStorage` (watched/reviewed
PRs, selected repos, tracked reviewer, theme, cloud-agent links, ntfy
channel, per-PR notes). These
sync across a viewer's devices through a tiny SQLite store keyed by
GitHub login (`PREFS_DB_PATH`); the browser keeps a `localStorage` copy
as an instant-render cache, and react-query folds the server's copy back
in on load and on refocus (last-write-wins).

> **Note — persistence is changing.** We're moving to a persistent
> data backend, so state will be stored rather than kept only in process
> memory. Today's behavior (in-memory per-user snapshots that vanish when
> the poller is reaped or the process restarts) is being replaced by a
> backing store that persists data across restarts. The relevant sections
> below describe the current in-memory model and will be updated as the
> persistent backend lands.

## Features

A full tour of what the app does, grouped by area.

### Sign-in & multi-tenancy

- **GitHub OAuth sign-in.** Anyone with a GitHub account signs in through
  the standard OAuth flow; unauthenticated visitors land on a "Sign in
  with GitHub" page.
- **No database, no shared token.** Each viewer's OAuth access token rides
  on a signed, HttpOnly session cookie. There's no server-side user store,
  so the only persistent secret is the cookie-signing key. _(Changing —
  see the persistence note above; a persistent backend is being added.)_
- **Per-user, in-memory snapshots.** Every viewer gets their own PR
  snapshot and background poller, scoped to the repos *their* token can
  see. State lives only in process memory. _(Changing — snapshots will be
  persisted in the new backend rather than lost on restart/reap.)_
- **Idle reaper.** A viewer's poller keeps running only while they're
  actively fetching the dashboard; once they stop (tab closed/hidden long
  enough), the reaper cancels the poller and frees their snapshot.
- **Dev-login shortcut.** An opt-in `DEV_LOGIN` mode mints a session
  straight from a personal access token, skipping the OAuth round-trip for
  local development. Off by default and meant to stay off in production.

### Live updates

- **Focus-aware polling.** react-query refetches the dashboard on the
  server's poll cadence while the tab is focused, and immediately on
  refocus.
- **Background throttling.** When the tab is hidden it stops polling
  entirely — unless you're watching a PR, in which case it drops to a slow
  background cadence to stay clear of GitHub's rate limit.
- **Cold-start warm-up.** On the first load (or after a reap) the server
  polls GitHub synchronously once, so the first paint has data instead of
  an empty board.
- **Manual refresh** forces a fresh synchronous poll on demand.
- **Rate-limit handling.** GitHub rate-limit errors surface in a banner
  (with the reset time) instead of blanking the board.

### The board

- **Three Trello-style columns**, shown only when non-empty:
  - **In Progress** — PRs you've opened that aren't ready for human review yet.
  - **Ready for review** — green-bordered column for PRs that are fully cooked.
  - **Approved** — PRs your tracked reviewer has approved (ready to merge).
- **MY PRs / REVIEWING tabs.** "MY PRs" includes PRs you authored or are
  assigned to; "REVIEWING" lists PRs where you've been requested as a
  reviewer, with a "requested N ago" hint. Each tab shows a live count and
  is reflected in the document title.
- **Inline review on the REVIEWING tab.** Selecting a PR you've been asked
  to review opens its diff in a read-only panel to the right (per-file
  hunks with line numbers, add/remove coloring), and each row carries an
  **Approve** button to sign off without leaving the dashboard.
- **Inbox-zero empty state** when there's nothing open.

### What each card shows

- **Checks pill** in `passed / pending / failed` form — green/yellow/red.
  Hover the failed count to see the actual failing check names.
- **Conflict badge** with a count, hidden when there are zero conflicts.
- **Two comment chips:** `H` (unresolved human comments, blue) and `B`
  (unresolved bot comments, black).
- **Preview link** when a preview deployment is detected, otherwise a
  muted "preview pending".
- **Reviewer chip** (see below) and per-card action buttons.
- **Draft PRs** render flat grey; **ready PRs** get a thick green border;
  manually-reviewed cards are dimmed.

### Reviewer tracking

- **Track one or more reviewers by GitHub login** (configured in Settings
  and synced across your devices, with a deploy-wide default). An approval
  from **any** tracked reviewer promotes a PR into the **Approved** column.
- **Add reviewers via a search-as-you-type picker:** Settings shows the
  tracked reviewers as removable chips and a debounced typeahead that
  searches GitHub users (proxied through the backend so your token never
  reaches the browser). Leave it empty to hide the chips entirely.
- **Per-card chip per reviewer, with three states each:** approved (green
  double-check), review-requested (blue single-check), or a yellow
  initial chip you can click to request that one reviewer. The card's
  primary **Request review(s)** button asks everyone still pending in one
  click on PRs you authored. On PRs assigned to you, **Notify reviewer**
  instead posts a comment mentioning every tracked reviewer.

### Per-card actions

- **Merge** (on approved PRs) via a confirmation dialog, using the
  configured merge method (`merge` / `squash` / `rebase`).
- **Ready for review** flips a draft PR out of draft.
- **Request review** from your tracked reviewer.

### Stacked PRs

- **Automatic stack detection.** PRs whose base branch is another
  dashboard PR's head are linked into a stack (a forest, structurally — no
  hardcoded `main`/`master`), with cycle detection.
- **Two rendering modes.** A stack whose members all land in the same
  column collapses into a single indented group; a stack split across
  columns shows an inline tree on each card with a per-node column badge.

### Cursor Cloud Agent QA

- **Launch a QA agent** for a PR straight from its card (editable prompt),
  running in the repo's Cursor-hosted cloud environment.
- **Link an existing agent** by pasting a `cursor.com/agents/` link.
- **Live run badge** — running / done / errored / cancelled — polled
  through the server so the shared `CURSOR_API_KEY` never reaches the
  browser, with a link to the run.
- **Walkthrough video.** When the run produced a recorded walkthrough
  artifact, a "video" button opens it via a short-lived presigned URL.

### Linear integration

- **Per-card Linear link.** When a PR title/body references a ticket (e.g.
  `ENG-1234`), the card links straight to the Linear issue.
- **Merge & mark done.** With a Linear API key configured, the merge
  dialog offers "merge & mark the linked ticket done", moving the issue
  into its team's completed state (best-effort — a Linear hiccup never
  fails the merge).

### Watch & notify

- **Watch a PR** to get a browser notification the moment its checks go
  green *and* its preview is deployed (i.e. it's actually clickable to
  review). Watching keeps the dashboard polling in the background so the
  ping fires even on an inactive tab; clicking the notification opens the PR.

### Per-browser preferences

All stored in `localStorage` — no server-side state:

- **Repo picker.** Show/hide repos across both tabs; a first-run picker
  appears until you choose.
- **Tracked reviewer** override.
- **Dark / light theme toggle** that respects your OS preference until you
  pick explicitly (and applies pre-paint to avoid a flash).
- **"Reviewed" marker** to manually dim a card you've dealt with.
- **Watched PRs** and **linked QA agents** (keyed per PR).
- **Active tab.**

## Layout

Three Trello-like columns (each shown only when it has cards):

- **In Progress** — PRs you've opened that aren't ready for human review yet.
- **Ready for review** — green-bordered column for PRs that are fully cooked.
- **Approved** — PRs your tracked reviewer has approved, ready to merge.

A PR is considered ready for human review when **all** of the following hold:

- All checks have finished, none are pending, none are failing (skipped checks
  are fine).
- There are no unresolved comments from humans or bots (bots are detected
  via GitHub's GraphQL `__typename: "Bot"` — `cursor`, `coderabbitai`,
  `github-actions`, `vercel`, etc. all qualify; everyone else is a human).
  Unresolved comments include unresolved review-thread comments **and** any
  generic PR conversation comment from a human that you haven't reacted to
  with any emoji — drop any reaction (👀, 👍, ❤️, 🚀, …) on a comment and
  it stops counting.
- The PR is not a draft.
- There are zero merge conflicts with the target branch.

Preview deployment status is shown on each card but does not affect column
placement. Watch notifications still wait for a preview URL (see **Watched
PRs** above).

(See **Features → What each card shows** above for the full card anatomy.)

## Repo layout

```
better-gh/
├── frontend/            # React + Vite SPA (TypeScript)
│   ├── index.html       # Vite entry (dashboard shell)
│   ├── login.html       # static "Sign in with GitHub" page
│   ├── styles.css       # shared Bauhaus stylesheet
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx     # React root + QueryClientProvider
│       ├── App.tsx      # top-level layout + tab/picker gating
│       ├── api/         # fetch client, types, react-query hooks
│       ├── hooks/       # localStorage stores + relative-time
│       └── components/  # TopBar, Board, PrCard, ReviewsList, ...
└── backend/             # FastAPI + GitHub poller
    ├── pyproject.toml
    ├── .env.example
    └── app/
        ├── main.py      # FastAPI app, lifespan, routes
        ├── auth.py      # GitHub OAuth + signed-cookie sessions
        ├── config.py    # pydantic-settings
        ├── model.py     # PR / Checks dataclasses + readiness rule
        ├── github.py    # async GraphQL client
        ├── preview.py   # deployment-comment parser
        ├── state.py     # per-user snapshot store + poller lifecycle
        ├── prefs.py     # SQLite per-user preference store (cross-device sync)
        ├── poller.py    # per-user background loop
        └── serialize.py # snapshot -> JSON for the SPA
```

## Run it

1. **Register a GitHub OAuth App.** Open
   <https://github.com/settings/developers> (or your org's "OAuth Apps"
   page) and click **New OAuth App**. Use:

   - **Application name**: anything (e.g. `better-gh`)
   - **Homepage URL**: `http://localhost:8000`
   - **Authorization callback URL**:
     `http://localhost:8000/auth/callback` (must match `GITHUB_OAUTH_REDIRECT_URL`
     byte for byte)

   Then **Generate a new client secret** and copy both the client id and
   secret -- you'll paste them into `.env` next.

2. **Boot the backend.**

   ```sh
   cd backend
   uv venv
   uv pip install -e .
   cp .env.example .env
   # edit .env: GITHUB_OAUTH_CLIENT_ID, GITHUB_OAUTH_CLIENT_SECRET,
   # and SESSION_SECRET are required. Generate the latter with:
   #   python -c 'import secrets; print(secrets.token_urlsafe(48))'
   uvicorn app.main:app --reload
   ```

If you don't have [uv](https://github.com/astral-sh/uv) handy, plain pip
works too (`python -m venv .venv && source .venv/bin/activate && pip install -e .`).

3. **Build (or dev-serve) the frontend.**

   ```sh
   cd frontend
   npm install
   npm run build      # writes frontend/dist, served by the backend at :8000
   ```

   For an iterative loop, run the Vite dev server instead — it proxies
   the API/auth routes through to uvicorn:

   ```sh
   npm run dev        # http://localhost:5173 (backend must be up on :8000)
   ```

A console script is installed alongside the package:

```sh
better-gh   # equivalent to: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000> (or the Vite dev server on :5173).
Unauthenticated visitors land on a "Sign in with GitHub" page; clicking
through bounces to GitHub's OAuth prompt, then back to the dashboard.
After that, react-query refetches the dashboard every five minutes while
the tab is focused (and immediately on refocus), and the per-user poller
keeps the in-memory snapshot fresh for as long as you keep fetching.

## Environment variables (backend)

All defined in `backend/.env.example` — copy to `backend/.env` and fill in.

| Var | Default | Notes |
|---|---|---|
| `GITHUB_OAUTH_CLIENT_ID` | _required_ | OAuth App client id. |
| `GITHUB_OAUTH_CLIENT_SECRET` | _required_ | OAuth App client secret. |
| `GITHUB_OAUTH_REDIRECT_URL` | `http://localhost:8000/auth/callback` | Must match the OAuth App's Authorization callback URL byte for byte. |
| `OAUTH_SCOPES` | `repo,read:org` | Scopes requested at sign-in. |
| `SESSION_SECRET` | _required_ | Used to sign session cookies. Rotate to log everyone out. |
| `SESSION_MAX_AGE_SECONDS` | `2592000` (30d) | Cookie lifetime. |
| `COOKIE_SECURE` | `false` | Flip to `true` behind HTTPS. |
| `GITHUB_GRAPHQL_URL` | `https://api.github.com/graphql` | Override for GHE. |
| `GITHUB_API_URL` | `https://api.github.com` | Override for GHE. |
| `POLL_INTERVAL_SECONDS` | `300` | How often each per-user poller polls (also the react-query refetch cadence while the tab is focused). |
| `IDLE_TTL_SECONDS` | `900` | How long a viewer's poller keeps running after their last `/api/dashboard` fetch before the idle reaper cancels it. |
| `MAX_PRS` | `50` | Top-N most recently updated open PRs. |
| `PREFS_DB_PATH` | `data/better-gh.sqlite3` | SQLite file holding synced per-user preferences (relative to the backend working dir). Mount a volume here in prod so settings survive restarts; `:memory:` for an ephemeral store. |
| `BOT_LOGINS` | `cursor,cursor[bot],coderabbitai,coderabbitai[bot]` | Comma-separated. |
| `PREVIEW_COMMENT_PREFIX` | `Preview Environment URL:` | Marker for the preview comment. |
| `REVIEWER_LOGIN` | `nicoraga1` | Default reviewer login(s) tracked on each card when a viewer hasn't configured their own. Comma-separate for several. Empty disables the chips + per-card request-review button. |
| `MERGE_METHOD` | `merge` | `merge` / `squash` / `rebase` for the per-card MERGE button. |
| `LINEAR_TICKET_PREFIX` | `ENG-` | Ticket prefix scanned in PR title/body (`<PREFIX>` + 3+ digits). Empty disables the Linear button. |
| `LINEAR_WORKSPACE_URL` | `https://linear.app/clearest` | Base URL; the Linear button links to `{base}/issue/{TICKET}`. |
| `LINEAR_API_KEY` | _(empty)_ | Personal API key (`lin_api_…`). When set, the merge dialog offers "merge & mark Linear ticket done", moving the linked issue into its team's completed state. Empty disables the action. |

## Routes

- `GET /` — dashboard SPA when signed in; redirect to `/login` otherwise.
- `GET /login` — minimal "Sign in with GitHub" page.
- `GET /auth/start` — redirects to GitHub's OAuth authorize URL.
- `GET /auth/callback` — exchanges the OAuth code, sets the session cookie.
- `POST /logout` — clears the session cookie + drops in-memory state.
- `GET /me` — `{login, avatar_url}` for the topbar chip (auth-gated).
- `GET /styles.css` — serves the stylesheet (used by the login page).
- `GET /api/dashboard?reviewers=<a,b,c>` — the full JSON snapshot the SPA
  renders (PRs, reviews, repo counts, last-updated, error); warms the
  per-user poller and touches the keep-alive on every call. `reviewers`
  is a comma-separated list of tracked logins (omit to use the deploy
  default; empty string to track nobody). The legacy single-login
  `?reviewer=` param is still accepted.
- `GET /api/users/search?q=<term>` — GitHub user typeahead for the
  reviewer picker, proxied with the viewer's token (returns
  `[{login, avatar_url}]`).
- `GET /api/prefs` — the signed-in viewer's synced preferences as a flat
  `{ key: value }` map (only keys they've set).
- `PUT /api/prefs` — upsert one or more preferences (`{ key: value }`;
  a `null` value deletes the key). Last-write-wins.
- `POST /refresh` — force a synchronous poll for the signed-in viewer.
- `POST /pulls/{owner}/{repo}/{number}/merge` · `…/ready-for-review` ·
  `…/request-review` (`{ reviewers: [...] }`) · `…/approve` — per-card
  mutations (then refresh the snapshot). `…/approve` submits an APPROVE
  review on a PR you've been asked to review.
- `GET /pulls/{owner}/{repo}/{number}/diff` — the PR's per-file diffs
  (`{files: [{filename, status, additions, deletions, patch, …}]}`) for
  the read-only review panel on the REVIEWING tab.

## Stack

- Backend: Python 3.11+, FastAPI, uvicorn, httpx, pydantic
- Frontend: React 18 + TypeScript + [Vite](https://vitejs.dev) +
  [@tanstack/react-query](https://tanstack.com/query)
- `npm run build` emits `frontend/dist`, which FastAPI serves; the Docker
  image builds it in a Node stage.

## Troubleshooting

- **"Sign-in failed: OAuth state mismatch"** — your `gh_oauth_state`
  cookie expired (10 min round-trip max) or `SESSION_SECRET` was
  rotated between the redirect and the callback. Hit `/login` again.
- **OAuth callback returns 400 from GitHub** — the
  `GITHUB_OAUTH_REDIRECT_URL` in `.env` must match the OAuth App's
  Authorization callback URL byte for byte (scheme, host, port, path).
- **401 / 403 from GitHub on the dashboard** — sign-in only requested
  `repo` + `read:org` by default; if you need access to repos in orgs
  with restricted third-party access, an org admin has to approve the
  OAuth App. Re-sign-in afterwards.
- **Dashboard loads but shows nothing / 404 on `/assets/...`** — the SPA
  bundle is missing. Run `npm run build` in `frontend/` (the Docker image
  does this in a Node stage). The backend falls back to the source
  `frontend/index.html` when `dist/` is absent, which only works under the
  Vite dev server.
- **Data doesn't refresh until I click REFRESH** — react-query only polls
  while the tab is focused (by design). Switching back to the tab triggers
  an immediate refetch.
- **Logged out unexpectedly after restart** — that shouldn't happen
  (the cookie is signed, not server-stored), but rotating
  `SESSION_SECRET` invalidates every cookie by design. Don't rotate
  on every deploy unless you mean to.
- **Card stuck in the wrong column** — the column is computed server-side
  in `app/serialize.py` (`PR.column_for`) and rendered by the `Board`
  component, which groups cards by that `column` value. If you see drift,
  check the reviewer being sent on `/api/dashboard?reviewer=` (an approval
  by the tracked reviewer promotes a PR to APPROVED).
