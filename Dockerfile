###############################################################################
# better-gh production image
#
# Single-stage on top of python:3.13-slim. The whole repo is small (one
# FastAPI app + static frontend), so a multi-stage build would add
# complexity without meaningfully shrinking the result.
#
# App Runner injects PORT (defaults to 8080) and expects the container
# to listen on it. We honour that via the CMD shell expansion below.
###############################################################################
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy backend + frontend together because the package install
# (hatchling -> wheel target = "app") needs the source tree present.
COPY backend /app/backend
COPY frontend /app/frontend

RUN pip install --no-cache-dir /app/backend

ENV PORT=8080
EXPOSE 8080

# WORKDIR matters: backend/app/main.py walks `__file__.parent.parent.parent`
# to find the frontend directory, so the container layout must mirror
# the repo layout (repo_root/{backend,frontend}).
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
