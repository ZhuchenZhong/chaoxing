#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.yml"

. "$ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
  chaoxing-manage import-legacy \
  --sql-path "${LEGACY_SQL_PATH:-/app/data/migration/user-data-export.sql}" \
  --report-dir "${LEGACY_REPORT_DIR:-/app/data/migration}"
