#!/usr/bin/env bash
# Dev-only helper: start a throwaway Postgres for local tests.
#   Container: pv-test-db   Port: 5433   user/pass/db: test/test/test_db
# Usage: scripts/test-db.sh [start|stop|status]   (default: start)
# Then: export TEST_DATABASE_URL=postgresql://test:test@localhost:5433/test_db
set -euo pipefail

NAME="pv-test-db"
PORT="5433"
IMAGE="postgres:16-alpine"
URL="postgresql://test:test@localhost:${PORT}/test_db"

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker is not installed or not on PATH" >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "error: Docker daemon is not running (start Docker Desktop)" >&2
    exit 1
fi

wait_ready() {
    for _ in $(seq 1 30); do
        if docker exec "$NAME" pg_isready -U test -d test_db >/dev/null 2>&1; then
            echo "$NAME is ready: $URL"
            return 0
        fi
        sleep 1
    done
    echo "error: $NAME did not become ready in 30s" >&2
    docker logs --tail 20 "$NAME" >&2 || true
    exit 1
}

cmd="${1:-start}"
case "$cmd" in
    start)
        if [ -n "$(docker ps -q -f "name=^${NAME}$")" ]; then
            echo "$NAME already running."
        elif [ -n "$(docker ps -aq -f "name=^${NAME}$")" ]; then
            echo "Starting existing container $NAME..."
            docker start "$NAME" >/dev/null
        else
            echo "Creating container $NAME on port $PORT..."
            docker run -d --name "$NAME" \
                -e POSTGRES_USER=test \
                -e POSTGRES_PASSWORD=test \
                -e POSTGRES_DB=test_db \
                -p "${PORT}:5432" \
                "$IMAGE" >/dev/null
        fi
        wait_ready
        ;;
    stop)
        docker rm -f "$NAME" >/dev/null 2>&1 && echo "Removed $NAME." || echo "$NAME not present."
        ;;
    status)
        docker ps -a -f "name=^${NAME}$"
        ;;
    *)
        echo "usage: $0 [start|stop|status]" >&2
        exit 2
        ;;
esac
