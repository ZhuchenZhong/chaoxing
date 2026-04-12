# Chaoxing Web Platform Rewrite

This repository is being rebuilt from the previous CLI-oriented Chaoxing project into a web-first platform.

## Current State

- Legacy CLI code has been archived under `bak/legacy-cli/`.
- Active rewrite work is tracked in TaskFlow under `.plan/confirmed/`.
- The rebuilt backend already exposes auth, account, user profile, course, study-run, wallet, and admin APIs for the web frontend.
- The UniApp H5 frontend is now implemented as the primary user/admin entrypoint under `frontend/src/` and builds successfully for H5.
- Production deployment assets now live under `deploy/`, including compose, env templates, Apache proxy notes, operational scripts, and the cutover runbook.
- The new platform will use:
  - `backend/` for the FastAPI, PostgreSQL, Redis, and worker stack
  - `frontend/` for the UniApp H5 entrypoint
  - `deploy/` for compose and cutover assets
  - `data/migration/` for legacy import assets

## Legacy Reference

The archived CLI implementation remains available for behavior reference:

- `bak/legacy-cli/`
- `E:\Project\ARCHIVE\chaoxing`

## Task Tracking

Execution is managed through TaskFlow files under `.plan/confirmed/` and mirrored in the human-readable files under `.plan/`.

## Migration Status

The legacy dump analysis is now wired into the rewrite:

- migration reports are generated into `data/migration/`
- current `user-data-export.sql` yields `6` users, `2` invites, `3` Chaoxing accounts, and `1349` wallet transactions
- all `3` migrated Chaoxing accounts need manual credential rebind because the legacy encrypted values are not reusable by the current backend cipher

## Operations

- `deploy/README.md` describes the production stack and the release flow
- `deploy/cutover-runbook.md` is the end-to-end cutover and rollback checklist
- `chaoxing-manage import-legacy` imports the archived SQL dump into the new schema
- `chaoxing-manage smoke` verifies `/health` and optional authenticated login
