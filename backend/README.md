# Backend

FastAPI backend for the Chaoxing web platform rewrite.

The backend will provide:

- authentication and account upgrade flow
- Chaoxing account management and course synchronization
- study task orchestration and worker execution
- wallet, invite, and admin APIs
- legacy SQL migration support

Operational entrypoints now include:

- `chaoxing-manage import-legacy`
- `chaoxing-manage smoke`
- the container image defined in `backend/Dockerfile`
