# Better GitHub UI

A clearer, calmer view of your open pull requests. Bauhaus-styled, HTMX-driven,
no backend (yet).

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

## Stack

- Static HTML + CSS
- [HTMX](https://htmx.org) loads `prs.html` into the page on first load and on
  Refresh.
- No build step. No backend. No JS framework.

## Run it

Just open `index.html` in a browser, or serve the directory:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

> HTMX is loaded from a CDN in `index.html`. Browsers may block `hx-get` against
> a `file://` URL — use the local server above for the live experience.

## Files

- `index.html` — page shell, header, two columns, refresh button
- `styles.css` — Bauhaus palette and components
- `prs.html` — mock PR fragment (the only data source for now)
