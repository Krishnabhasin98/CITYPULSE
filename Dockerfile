# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the React frontend into static assets.
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /build/frontend

# Copy manifests first so `npm ci` is cached until dependencies actually change.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# VITE_API_URL is intentionally left unset: the app then calls its own origin,
# which is the same container serving these files.
RUN npm run build


# ---------------------------------------------------------------------------
# Stage 2 — Python runtime serving API + built frontend from one process.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    SERVE_FRONTEND=true \
    DATABASE_URL=sqlite:////data/citypulse.db \
    UPLOAD_DIR=/data/uploads \
    CITYPULSE_CACHE_DIR=/data/cache

WORKDIR /app

# curl is used by the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

COPY backend/ ./backend/
COPY ai/ ./ai/

# The API imports the `ai` package from the repository root, so run uvicorn
# from /app (not backend/) — the same layout the local scripts use.
COPY --from=frontend /build/frontend/dist ./frontend/dist

RUN mkdir -p /data/uploads /data/cache \
    && useradd --create-home --uid 10001 citypulse \
    && chown -R citypulse:citypulse /app /data
USER citypulse

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
