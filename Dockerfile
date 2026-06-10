###############################################################################
# better-gh production image
#
# Two stages:
#   1. node  -> build the React + Vite SPA into frontend/dist
#   2. python -> install the FastAPI backend and serve the built SPA
#
# App Runner injects PORT (defaults to 8080) and expects the container to
# listen on it. We honour that via the CMD shell expansion below.
###############################################################################

# --- Stage 1: build the frontend ------------------------------------------
FROM node:20-slim AS frontend

WORKDIR /app/frontend

# Install deps from the lockfile first for layer caching.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Then the sources (node_modules / dist are excluded via .dockerignore)
# and produce the production build at /app/frontend/dist.
COPY frontend/ ./
RUN npm run build


# --- Stage 2: the runtime image -------------------------------------------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy backend + frontend sources together because the package install
# (hatchling -> wheel target = "app") needs the source tree present, and
# the backend still serves the source styles.css / login.html / icons.
COPY backend /app/backend
COPY frontend /app/frontend

# Drop in the built SPA from the node stage (the source tree excludes it).
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN pip install --no-cache-dir /app/backend

ENV PORT=8080
EXPOSE 8080

# Per-user preferences are persisted to a SQLite file under PREFS_DB_PATH
# (default backend/data/better-gh.sqlite3, relative to the WORKDIR below).
# Declare it as a volume so the synced settings survive container
# restarts; mount a host path or named volume here in production.
VOLUME ["/app/backend/data"]

# WORKDIR matters: backend/app/main.py walks `__file__.parent.parent.parent`
# to find the frontend directory, so the container layout must mirror
# the repo layout (repo_root/{backend,frontend}).
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
