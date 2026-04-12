# Architecture

The rewrite uses a web-first platform architecture:

- `frontend/` serves as the H5 entrypoint built with UniApp.
- `backend/` hosts the FastAPI application, domain services, and worker runtime.
- `deploy/` contains compose and cutover assets.
- `data/migration/` holds legacy migration inputs and migration outputs.

Detailed component contracts will be expanded as the backend foundation and domain schema land.
