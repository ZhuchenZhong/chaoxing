# Chaoxing Web Cutover Runbook

## Pre-flight

1. Copy `deploy/.env.example` to `deploy/.env`.
2. Replace `JWT_SECRET`, `POSTGRES_PASSWORD`, `CORS_ORIGINS`, and optional `SMOKE_USERNAME` / `SMOKE_PASSWORD`.
3. Confirm the legacy dump exists at `data/migration/user-data-export.sql` or update `LEGACY_SQL_PATH`.
4. Confirm Apache has `proxy`, `proxy_http`, and `headers` enabled.

## Bring-up Sequence

1. `deploy/scripts/up.sh` — API container auto-runs `alembic upgrade head` before starting
2. `deploy/scripts/import-legacy.sh`
3. `deploy/scripts/smoke-test.sh`

## Smoke Checklist

- `GET /health` returns `{"status":"healthy", ...}`
- login works for one migrated or seeded administrator account
- `/api/v1/auth/me` returns the expected role
- H5 landing page loads through the frontend container
- one Chaoxing account can be re-verified from the UI
- one course sync request succeeds
- one study run can be created and its detail page shows polling updates

## Apache Cutover

1. Copy `deploy/apache/chaoxing.conf` into the Apache vhost directory.
2. Replace `ServerName` and, if needed, the loopback bind ports.
3. Reload Apache after the Docker stack passes smoke checks.

## Rollback

1. Disable the new Apache vhost and reload Apache.
2. Stop the new stack with `docker compose --env-file deploy/.env -f deploy/docker-compose.yml down`.
3. Restore the previous CLI or legacy-web entrypoint.
4. Keep `postgres-data` intact unless the rollback explicitly requires discarding the new environment.

## Post-cutover Verification

- migrated users can log in and are forced to change password on first access
- migrated Chaoxing accounts are visible and clearly require rebind when credentials are not reusable
- admin recharge review and invite management pages render correctly
- no worker crash loop is visible in `docker compose ps` or `docker compose logs worker`
