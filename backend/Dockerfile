# syntax=docker/dockerfile:1
# ---------- Stage 1: build Python dependencies into a virtualenv ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    SCAN_WORKDIR=/tmp/project-verification \
    GIT_TERMINAL_PROMPT=0

# git is required: the scanner clones repositories. libpq5 for psycopg runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --create-home --home-dir /home/appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p "$SCAN_WORKDIR" \
    && chown -R appuser:appuser "$SCAN_WORKDIR"

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# Exactly ONE worker: the scan executor, the startup reset of interrupted scans and the
# startup purge of stale clone directories are process-local (see app/services/scan_service.py).
# Behind a reverse proxy add `--proxy-headers --forwarded-allow-ips=<proxy ip>` (NEVER "*"),
# otherwise every client shares the proxy's rate-limit bucket (see app/rate_limit.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
