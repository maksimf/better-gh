# Better GitHub UI

A clearer, calmer view of your open pull requests. Bauhaus-styled,
HTMX-driven, with a tiny FastAPI backend that polls GitHub and pushes
updates to the browser over Server-Sent Events.

Anyone with a GitHub account can sign in via OAuth. No database: each
viewer's access token rides on a signed HttpOnly cookie, and their PR
snapshot lives only in process memory for as long as they have an SSE
connection open.

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
├── frontend/            # static UI shell (HTMX + SSE extension)
│   ├── index.html
│   └── styles.css
└── backend/             # FastAPI + GitHub poller
    ├── pyproject.toml
    ├── .env.example
    ├── app/
    │   ├── main.py      # FastAPI app, lifespan, routes
    │   ├── auth.py      # GitHub OAuth + signed-cookie sessions
    │   ├── config.py    # pydantic-settings
    │   ├── model.py     # PR / Checks dataclasses + readiness rule
    │   ├── github.py    # async GraphQL client
    │   ├── preview.py   # deployment-comment parser
    │   ├── state.py     # per-user snapshot store + SSE registry
    │   ├── poller.py    # per-user background loop
    │   └── render.py    # Jinja env
    └── templates/
        └── prs.html     # PR-card fragment template
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

A console script is installed alongside the package:

```sh
better-gh   # equivalent to: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. Unauthenticated visitors land on a
"Sign in with GitHub" page; clicking through bounces to GitHub's OAuth
prompt, then back to the dashboard. After that, SSE keeps the page live
and the per-user poller refreshes from GitHub every five minutes for
as long as you have a tab open.

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
| `POLL_INTERVAL_SECONDS` | `300` | How often each per-user poller polls. |
| `MAX_PRS` | `50` | Top-N most recently updated open PRs. |
| `BOT_LOGINS` | `cursor,cursor[bot],coderabbitai,coderabbitai[bot]` | Comma-separated. |
| `PREVIEW_COMMENT_PREFIX` | `Preview Environment URL:` | Marker for the preview comment. |
| `REVIEWER_LOGIN` | `nicoraga1` | Reviewer tracked on each card. Empty disables the chip + per-card request-review button. |
| `MERGE_METHOD` | `merge` | `merge` / `squash` / `rebase` for the per-card MERGE button. |
| `LINEAR_TICKET_PREFIX` | `ENG-` | Ticket prefix scanned in PR title/body (`<PREFIX>` + 3+ digits). Empty disables the Linear button. |
| `LINEAR_WORKSPACE_URL` | `https://linear.app/clearest` | Base URL; the Linear button links to `{base}/issue/{TICKET}`. |

## Routes

- `GET /` — landing page when signed out; dashboard when signed in.
- `GET /login` — minimal "Sign in with GitHub" page.
- `GET /auth/start` — redirects to GitHub's OAuth authorize URL.
- `GET /auth/callback` — exchanges the OAuth code, sets the session cookie.
- `POST /logout` — clears the session cookie + drops in-memory state.
- `GET /me` — `{login, avatar_url}` for the topbar chip (auth-gated).
- `GET /styles.css` — serves the stylesheet (public; used by both pages).
- `GET /prs.html` — Jinja-rendered PR cards for the signed-in viewer.
- `GET /events` — SSE stream; bootstraps a per-user poller on first connect.
- `POST /refresh` — kick off an out-of-band poll for the signed-in viewer.

## Stack

- Python 3.11+, FastAPI, uvicorn, httpx, pydantic, jinja2, sse-starlette
- Static HTML + CSS + [HTMX](https://htmx.org) (with the SSE extension)
- No build step on the frontend.

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
- **`/events` shows nothing** — make sure the HTMX SSE extension script is
  loaded (it lives next to the main `htmx.org` bundle). Browsers will also
  silently disconnect if your reverse proxy buffers responses; uvicorn alone
  is fine.
- **Logged out unexpectedly after restart** — that shouldn't happen
  (the cookie is signed, not server-stored), but rotating
  `SESSION_SECRET` invalidates every cookie by design. Don't rotate
  on every deploy unless you mean to.
- **Card stuck in the wrong column** — the column is driven by
  `data-column` on each `<article>`. If you see drift, check that the
  template's class list matches `styles.css` (it should be unchanged from
  the original mock).
