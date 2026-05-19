# Better GitHub UI

A clearer, calmer view of your open pull requests. Bauhaus-styled,
HTMX-driven, with a tiny FastAPI backend that polls GitHub and pushes
updates to the browser over Server-Sent Events.

## Layout

Two trello-like columns:

- **In Progress** — PRs you've opened that aren't ready for human review yet.
- **Ready for review** — green-bordered column for PRs that are fully cooked.

A PR is considered ready for human review when **all** of the following hold:

- All checks have finished, none are pending, none are failing (skipped checks
  are fine).
- There are no unresolved comments from humans or bots (bots = `cursor` and
  `coderabbit`; everyone else is a human).
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
    │   ├── config.py    # pydantic-settings
    │   ├── model.py     # PR / Checks dataclasses + readiness rule
    │   ├── github.py    # async GraphQL client
    │   ├── preview.py   # deployment-comment parser
    │   ├── state.py     # snapshot store + SSE registry
    │   ├── poller.py    # background loop
    │   └── render.py    # Jinja env
    └── templates/
        └── prs.html     # PR-card fragment template
```

## Run it

```sh
cd backend
uv venv
uv pip install -e .
cp .env.example .env
# then edit .env and set GITHUB_TOKEN
uvicorn app.main:app --reload
```

If you don't have [uv](https://github.com/astral-sh/uv) handy, plain pip
works too (`python -m venv .venv && source .venv/bin/activate && pip install -e .`).

A console script is installed alongside the package:

```sh
better-gh   # equivalent to: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open <http://localhost:8000>. The first paint hits `/prs.html`; after
that, SSE keeps the page live and the poller refreshes from GitHub every
five minutes.

## Environment variables (backend)

All defined in `backend/.env.example` — copy to `backend/.env` and fill in.

| Var | Default | Notes |
|---|---|---|
| `GITHUB_TOKEN` | _required_ | PAT used for the GraphQL API. |
| `GITHUB_GRAPHQL_URL` | `https://api.github.com/graphql` | Override for GHE. |
| `POLL_INTERVAL_SECONDS` | `300` | How often the poller polls. |
| `MAX_PRS` | `50` | Top-N most recently updated open PRs. |
| `BOT_LOGINS` | `cursor,cursor[bot],coderabbitai,coderabbitai[bot]` | Comma-separated. |
| `PREVIEW_COMMENT_PREFIX` | `Preview Environment URL:` | Marker for the preview comment. |
| `LINEAR_TICKET_PREFIX` | `ENG-` | Ticket prefix scanned in PR title/body (`<PREFIX>` + 3+ digits). Empty disables the Linear button. |
| `LINEAR_WORKSPACE_URL` | `https://linear.app/clearest` | Base URL; the Linear button links to `{base}/issue/{TICKET}`. |

## Routes

- `GET /` — serves `frontend/index.html`.
- `GET /styles.css` — serves the stylesheet.
- `GET /prs.html` — Jinja-rendered PR cards (cold start + Refresh button).
- `GET /events` — SSE stream; each subscriber gets the current snapshot
  immediately and any subsequent change.
- `POST /refresh` — kick off an out-of-band poll; returns 204.

## Stack

- Python 3.11+, FastAPI, uvicorn, httpx, pydantic, jinja2, sse-starlette
- Static HTML + CSS + [HTMX](https://htmx.org) (with the SSE extension)
- No build step on the frontend.

## Troubleshooting

- **401 / 403 from GitHub** — your PAT needs `repo` + `read:org` (classic),
  or fine-grained PR read across the orgs/repos you care about. Without it
  the poller logs an error every interval and the dashboard stays empty.
- **`/events` shows nothing** — make sure the HTMX SSE extension script is
  loaded (it lives next to the main `htmx.org` bundle). Browsers will also
  silently disconnect if your reverse proxy buffers responses; uvicorn alone
  is fine.
- **Card stuck in the wrong column** — the column is driven by
  `data-column` on each `<article>`. If you see drift, check that the
  template's class list matches `styles.css` (it should be unchanged from
  the original mock).
