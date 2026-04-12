# Deploy

This directory now contains the production-oriented deployment and cutover assets for the Chaoxing web rewrite.

## Files

- `docker-compose.yml`: production stack for `postgres`, `redis`, `api`, `worker`, and `frontend`
- `.env.example`: environment template for compose and backend runtime
- `apache/chaoxing.conf`: reverse-proxy example for Apache fronting the Docker stack
- `scripts/up.sh`: start the full stack
- `scripts/migrate.sh`: apply Alembic migrations
- `scripts/import-legacy.sh`: import the archived `user-data-export.sql` dump
- `scripts/smoke-test.sh`: verify `/health` and optional authenticated login

## Expected Release Flow

1. Copy `deploy/.env.example` to `deploy/.env` and fill secrets, DB credentials, domain CORS, and optional smoke-test credentials.
2. Run `deploy/scripts/up.sh` — the API entrypoint runs Alembic migrations automatically before starting uvicorn.
3. Run `deploy/scripts/import-legacy.sh` if this is the main cutover from the legacy platform.
4. Run `deploy/scripts/smoke-test.sh`.
5. Put Apache in front of the loopback-bound `api` and `frontend` ports using `apache/chaoxing.conf`.

> To run migrations manually (e.g. before a rolling update), use `deploy/scripts/migrate.sh`.
