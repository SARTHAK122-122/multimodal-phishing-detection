# =====================================================================
# Python AI service (FastAPI) - multimodal phishing analysis pipelines.
#
# Build context is the ai-service directory; trained model artifacts are
# NOT baked in - they are mounted at /app/models (see docker-compose.yml)
# so retraining never requires an image rebuild.
# =====================================================================
# Base pinned to bookworm: Playwright 1.49's dependency list matches Debian 12,
# while slim:latest has moved on and --with-deps then fails to resolve packages.
FROM python:3.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PROJECT_ROOT=/app \
    MODEL_DIR=/app/models \
    UPLOAD_DIR=/app/uploads \
    DATASETS_DIR=/app/datasets

WORKDIR /app

# System libs: lxml/opencv wheels are self-contained; curl for HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Generous retries/timeout: large scientific wheels (numpy, pandas, torch-sized
# deps) must survive slow or flaky links without failing the whole build.
# The BuildKit cache mount makes retries incremental instead of re-downloading.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --retries 10 --timeout 180 -r requirements.txt

# Headless Chromium for the screenshot/render modality (Playwright).
# apt-get update must run in the same layer: --with-deps installs system
# packages and the earlier layer's package lists were pruned.
RUN apt-get update \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Non-root user; the app only ever writes under /app/uploads.
RUN useradd --create-home --shell /usr/sbin/nologin phish \
    && mkdir -p /app/uploads /app/models \
    && chown -R phish:phish /app/uploads /app/models

COPY app ./app
COPY training ./training
# Tests are included so `docker compose run ai-service pytest` works too.
COPY tests ./tests

USER phish
EXPOSE 8000

# Inside the compose network the service listens on 0.0.0.0 so the backend can
# reach it, but it is NOT published to the host (no ports: mapping). For local,
# non-Docker runs scripts/start-ai-service.ps1 binds 127.0.0.1 instead.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
