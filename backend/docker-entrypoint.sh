#!/bin/sh
# Backend container entrypoint: prepare scan workdir, run migrations, then exec CMD.
set -eu

SCAN_WORKDIR="${SCAN_WORKDIR:-/tmp/project-verification}"
mkdir -p "$SCAN_WORKDIR"

echo "[entrypoint] Running database migrations (alembic upgrade head)..."
alembic upgrade head

if [ "$#" -eq 0 ]; then
    # Single worker only: scan state cleanup on startup is process-local.
    # Behind a reverse proxy append: --proxy-headers --forwarded-allow-ips=<proxy ip>
    # (never "*": clients could spoof X-Forwarded-For and evade rate limits).
    set -- uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
fi

echo "[entrypoint] Starting: $*"
exec "$@"
