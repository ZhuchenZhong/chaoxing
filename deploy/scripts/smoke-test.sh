#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"

. "$ENV_FILE"

set -- chaoxing-manage smoke --base-url "http://api:8000"

if [ -n "${SMOKE_USERNAME:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
  set -- "$@" --username "$SMOKE_USERNAME" --password "$SMOKE_PASSWORD"
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api "$@"
