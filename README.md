# Better GitHub UI

A clearer, calmer view of your open pull requests. Bauhaus-styled, a
React + react-query single-page app backed by a tiny FastAPI service
that polls GitHub and serves the snapshot as JSON.

react-query drives the live updates: it polls the dashboard while the
tab is focused, stops entirely when the tab is hidden, and refetches the
moment you switch back to it.

Anyone with a GitHub account can sign in via OAuth. No database: each
viewer's access token rides on a signed HttpOnly cookie, and their PR
snapshot lives only in process memory for as long as they keep fetching
(an idle reaper cancels the per-user poller once they stop).

## Layout

Two trello-like columns:

- **In Progress** — PRs you've opened that aren't ready for human review yet.
- **Ready for review** — green-bordered column for PRs that are fully cooked.

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
- The PR's preview is deployed.
- There are zero merge conflicts with the target branch.

## What each card shows

- Checks pill in `A/B/C` form: green = finished, yellow = pending/in progress,
  red = failed.
- Two comment chips: `H:n` (humans, blue) and `B:n` (bots, black).
- Preview link if deployed, otherwise muted "preview is pending".
- Red exclamation block with the conflict count, hidden when zero.
- Draft PRs are flat grey.
- Ready PRs get a thick green border.

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
| `BOT_LOGINS` | `cursor,cursor[bot],coderabbitai,coderabbitai[bot]` | Comma-separated. |
| `PREVIEW_COMMENT_PREFIX` | `Preview Environment URL:` | Marker for the preview comment. |
| `REVIEWER_LOGIN` | `nicoraga1` | Reviewer tracked on each card. Empty disables the chip + per-card request-review button. |
| `MERGE_METHOD` | `merge` | `merge` / `squash` / `rebase` for the per-card MERGE button. |
| `LINEAR_TICKET_PREFIX` | `ENG-` | Ticket prefix scanned in PR title/body (`<PREFIX>` + 3+ digits). Empty disables the Linear button. |
| `LINEAR_WORKSPACE_URL` | `https://linear.app/clearest` | Base URL; the Linear button links to `{base}/issue/{TICKET}`. |

## Routes

- `GET /` — dashboard SPA when signed in; redirect to `/login` otherwise.
- `GET /login` — minimal "Sign in with GitHub" page.
- `GET /auth/start` — redirects to GitHub's OAuth authorize URL.
- `GET /auth/callback` — exchanges the OAuth code, sets the session cookie.
- `POST /logout` — clears the session cookie + drops in-memory state.
- `GET /me` — `{login, avatar_url}` for the topbar chip (auth-gated).
- `GET /styles.css` — serves the stylesheet (used by the login page).
- `GET /api/dashboard?reviewer=<login>` — the full JSON snapshot the SPA
  renders (PRs, reviews, repo counts, last-updated, error); warms the
  per-user poller and touches the keep-alive on every call.
- `POST /refresh` — force a synchronous poll for the signed-in viewer.
- `POST /pulls/{owner}/{repo}/{number}/merge` · `…/ready-for-review` ·
  `…/request-review` — per-card mutations (then refresh the snapshot).

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
