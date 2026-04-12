#!/bin/sh
set -e

# Run Alembic migrations only when starting the API server.
# The worker depends on the api service being healthy, so by the time
# the worker container starts, migrations are guaranteed to be complete.
if [ "$1" = "uvicorn" ]; then
    echo "[entrypoint] Running Alembic migrations…"
    alembic upgrade head
fi

exec "$@"
