#!/usr/bin/env python
"""
E2E Smoke Test — verifies the full Chaoxing stack works end-to-end.

Usage:
    python deploy/smoke_test.py            # from repo root
    python deploy/smoke_test.py --no-frontend  # skip frontend build check

Starts a temporary backend server on a random port, runs all API tests against
it, then tears everything down.  Uses SQLite so neither Postgres nor Redis is
required.

Exit code 0  → all tests passed
Exit code 1  → at least one failure
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
PYTHON_EXE = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"

if not PYTHON_EXE.exists():
    # Unix fallback
    PYTHON_EXE = BACKEND_DIR / ".venv" / "bin" / "python"

SMOKE_DB_NAME = f"smoke_test_{uuid.uuid4().hex[:8]}.db"
SMOKE_DB_PATH = BACKEND_DIR / SMOKE_DB_NAME

# ---------------------------------------------------------------------------
# Pretty output helpers
# ---------------------------------------------------------------------------
_results: list[tuple[str, bool, str]] = []


def _log(icon: str, msg: str) -> None:
    print(f"  {icon} {msg}", flush=True)


def _pass(name: str, detail: str = "") -> None:
    _results.append((name, True, detail))
    _log("✅", f"PASS  {name}" + (f"  ({detail})" if detail else ""))


def _fail(name: str, detail: str = "") -> None:
    _results.append((name, False, detail))
    _log("❌", f"FAIL  {name}" + (f"  ({detail})" if detail else ""))


def _section(title: str) -> None:
    print(f"\n{'─' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'─' * 60}", flush=True)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_backend(port: int) -> subprocess.Popen:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///./{SMOKE_DB_NAME}",
        "JWT_SECRET": "smoke-test-secret-key-not-for-production",
        "DEBUG": "true",
        "CORS_ORIGINS": "*",
    }
    cmd = [
        str(PYTHON_EXE), "-m", "uvicorn",
        "chaoxing.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    return proc


def _stop_backend(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Poll the health endpoint until it responds or we time out."""
    import httpx

    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException, OSError):
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# DB bootstrap — create tables + seed invite code
# ---------------------------------------------------------------------------
async def _bootstrap_db(port: int) -> None:
    """Create all tables and insert a usable invite code via SQLAlchemy."""
    # We must override settings *before* importing anything that reads them.
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./{SMOKE_DB_NAME}"
    os.environ["JWT_SECRET"] = "smoke-test-secret-key-not-for-production"

    # Import inside function so env vars are set first.
    # We need to invalidate the cached settings singleton.
    from chaoxing.config.settings import get_settings

    get_settings.cache_clear()

    from chaoxing.models.base import BaseModel as Base
    from chaoxing.models import Invite  # noqa: F401 – ensure model is registered
    from chaoxing import models  # noqa: F401 – register all models
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = f"sqlite+aiosqlite:///./{SMOKE_DB_NAME}"
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed an invite code for registration tests
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from datetime import datetime, timezone

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        invite = Invite(
            code="smoke-test-invite",
            max_uses=100,
            used_count=0,
            bonus_credits=0,
            is_active=True,
            expires_at=None,
            created_at=datetime.now(timezone.utc),
            created_by_user_id=None,
        )
        session.add(invite)
        await session.commit()

    await engine.dispose()


# ---------------------------------------------------------------------------
# API smoke tests
# ---------------------------------------------------------------------------
def _run_api_tests(port: int) -> None:
    import httpx

    base = f"http://127.0.0.1:{port}"
    client = httpx.Client(base_url=base, timeout=15)
    token: str | None = None
    username = f"smoke_{uuid.uuid4().hex[:6]}"
    email = f"{username}@smoke-test.local"
    password = "SmokeTestP@ss123"

    # 1) GET /health
    try:
        r = client.get("/health")
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert body.get("status") == "healthy"
        _pass("GET /health", f"version={body.get('version')}")
    except Exception as exc:
        _fail("GET /health", str(exc))

    # 2) GET /api/v1/ — root
    try:
        r = client.get("/api/v1/")
        assert r.status_code == 200, f"status={r.status_code}"
        _pass("GET /api/v1/", r.json().get("message", ""))
    except Exception as exc:
        _fail("GET /api/v1/", str(exc))

    # 3) POST /api/v1/auth/register
    try:
        r = client.post("/api/v1/auth/register", json={
            "email": email,
            "username": username,
            "display_name": "Smoke Tester",
            "password": password,
            "invite_code": "smoke-test-invite",
        })
        assert r.status_code == 201, f"status={r.status_code} body={r.text}"
        body = r.json()
        assert body["username"] == username
        _pass("POST /api/v1/auth/register", f"user_id={body.get('id')}")
    except Exception as exc:
        _fail("POST /api/v1/auth/register", str(exc))

    # 4) POST /api/v1/auth/login
    try:
        r = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password,
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        body = r.json()
        token = body.get("access_token")
        assert token, "no access_token returned"
        _pass("POST /api/v1/auth/login", "token obtained")
    except Exception as exc:
        _fail("POST /api/v1/auth/login", str(exc))

    if not token:
        _fail("SKIP remaining authenticated tests", "no token")
        client.close()
        return

    auth_headers = {"Authorization": f"Bearer {token}"}

    # 5) GET /api/v1/auth/me
    try:
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert body["username"] == username
        assert body["email"] == email
        _pass("GET /api/v1/auth/me", f"user={body['username']}")
    except Exception as exc:
        _fail("GET /api/v1/auth/me", str(exc))

    # 6) GET /api/v1/accounts/ — empty list
    try:
        r = client.get("/api/v1/accounts", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert isinstance(body, list)
        _pass("GET /api/v1/accounts", f"count={len(body)}")
    except Exception as exc:
        _fail("GET /api/v1/accounts", str(exc))

    # 7) POST /api/v1/accounts/ — create account (password type)
    account_id = None
    try:
        r = client.post("/api/v1/accounts", headers=auth_headers, json={
            "display_name": "Smoke CX Account",
            "auth_type": "password",
            "username": "fake_cx_user",
            "password": "fake_cx_pass",
        })
        assert r.status_code == 201, f"status={r.status_code} body={r.text}"
        body = r.json()
        account_id = body.get("id")
        assert account_id is not None
        _pass("POST /api/v1/accounts", f"account_id={account_id}")
    except Exception as exc:
        _fail("POST /api/v1/accounts", str(exc))

    # 8) GET /api/v1/users/notification-config
    try:
        r = client.get("/api/v1/users/notification-config", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert "providers" in body
        _pass("GET /api/v1/users/notification-config", f"providers={len(body['providers'])}")
    except Exception as exc:
        _fail("GET /api/v1/users/notification-config", str(exc))

    # 9) GET /api/v1/study-runs/
    try:
        r = client.get("/api/v1/study-runs", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert isinstance(body, list)
        _pass("GET /api/v1/study-runs", f"count={len(body)}")
    except Exception as exc:
        _fail("GET /api/v1/study-runs", str(exc))

    # 10) GET /api/v1/users/profile
    try:
        r = client.get("/api/v1/users/profile", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert body["username"] == username
        _pass("GET /api/v1/users/profile", "OK")
    except Exception as exc:
        _fail("GET /api/v1/users/profile", str(exc))

    # 11) GET /api/v1/users/study-config (auto-creates default)
    try:
        r = client.get("/api/v1/users/study-config", headers=auth_headers)
        assert r.status_code == 200, f"status={r.status_code}"
        body = r.json()
        assert body.get("profile_name") == "default"
        _pass("GET /api/v1/users/study-config", f"speed={body.get('speed')}")
    except Exception as exc:
        _fail("GET /api/v1/users/study-config", str(exc))

    # 12) DELETE /api/v1/accounts/{account_id} — cleanup
    if account_id is not None:
        try:
            r = client.delete(f"/api/v1/accounts/{account_id}", headers=auth_headers)
            assert r.status_code == 200, f"status={r.status_code}"
            _pass(f"DELETE /api/v1/accounts/{account_id}", "cleaned up")
        except Exception as exc:
            _fail(f"DELETE /api/v1/accounts/{account_id}", str(exc))

    client.close()


# ---------------------------------------------------------------------------
# Frontend build check
# ---------------------------------------------------------------------------
def _run_frontend_check() -> None:
    _section("Frontend Smoke Test")

    h5_index = FRONTEND_DIR / "dist" / "build" / "h5" / "index.html"
    if h5_index.exists():
        _pass("Frontend H5 build exists", str(h5_index))
    else:
        _log("ℹ️", "No existing H5 build found — running npm run build:h5 …")
        try:
            result = subprocess.run(
                ["npm", "run", "build:h5"],
                cwd=str(FRONTEND_DIR),
                timeout=120,
                capture_output=True,
                text=True,
                shell=True,
            )
            if result.returncode == 0 and h5_index.exists():
                _pass("npm run build:h5", "built successfully")
            else:
                detail = (result.stderr or result.stdout or "")[-300:]
                _fail("npm run build:h5", detail.strip())
        except subprocess.TimeoutExpired:
            _fail("npm run build:h5", "timed out after 120s")
        except Exception as exc:
            _fail("npm run build:h5", str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="E2E smoke test for the Chaoxing platform")
    parser.add_argument("--no-frontend", action="store_true", help="Skip frontend build check")
    args = parser.parse_args()

    print(f"\n🔥  Chaoxing E2E Smoke Test\n", flush=True)

    # ── Bootstrap DB ──────────────────────────────────────────────────────
    _section("Bootstrap")

    # Must run from backend dir so the SQLite file is created there
    original_cwd = os.getcwd()
    os.chdir(str(BACKEND_DIR))

    # Add backend src to sys.path so we can import chaoxing
    src_dir = str(BACKEND_DIR / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        asyncio.run(_bootstrap_db(0))
        _pass("Database bootstrap", SMOKE_DB_NAME)
    except Exception as exc:
        _fail("Database bootstrap", str(exc))
        os.chdir(original_cwd)
        _cleanup()
        return 1

    # ── Start backend ─────────────────────────────────────────────────────
    _section("Backend Server")

    port = _free_port()
    proc = _start_backend(port)
    _log("🚀", f"Starting backend on port {port} (PID {proc.pid}) …")

    try:
        if _wait_for_server(port, timeout=30):
            _pass("Backend server started", f"http://127.0.0.1:{port}")
        else:
            output = ""
            if proc.stdout:
                proc.stdout.close()
            _fail("Backend server startup", "timed out waiting for /health")
            _stop_backend(proc)
            os.chdir(original_cwd)
            _cleanup()
            return 1

        # ── Run API tests ─────────────────────────────────────────────────
        _section("API Smoke Tests")
        _run_api_tests(port)

    finally:
        _log("🛑", "Stopping backend server …")
        _stop_backend(proc)

    os.chdir(original_cwd)

    # ── Frontend ──────────────────────────────────────────────────────────
    if not args.no_frontend:
        _run_frontend_check()

    # ── Summary ───────────────────────────────────────────────────────────
    _section("Summary")
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    total = len(_results)
    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}\n", flush=True)

    if failed:
        print("  Failed tests:", flush=True)
        for name, ok, detail in _results:
            if not ok:
                print(f"    ❌ {name}: {detail}", flush=True)
        print(flush=True)

    _cleanup()

    return 1 if failed else 0


def _cleanup() -> None:
    """Remove temporary smoke-test DB file(s)."""
    for p in BACKEND_DIR.glob("smoke_test_*.db*"):
        try:
            p.unlink()
            _log("🧹", f"Removed {p.name}")
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
