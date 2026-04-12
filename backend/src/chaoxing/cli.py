from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import typer

from .db.database import AsyncSessionLocal
from .migration.legacy_import import (
    apply_migration,
    build_migration_bundle,
    parse_legacy_sql,
    write_migration_reports,
)

app = typer.Typer(help="Operational commands for the Chaoxing web platform.")


@app.command("import-legacy")
def import_legacy(
    sql_path: Path = typer.Option(..., exists=True, readable=True, help="Path to legacy SQL dump."),
    report_dir: Path = typer.Option(
        Path("data/migration"),
        file_okay=False,
        dir_okay=True,
        help="Directory where migration reports should be written.",
    ),
) -> None:
    asyncio.run(_import_legacy(sql_path=sql_path, report_dir=report_dir))


@app.command("smoke")
def smoke(
    base_url: str = typer.Option("http://127.0.0.1:8000", help="API root base URL."),
    username: str | None = typer.Option(None, help="Optional username for authenticated smoke checks."),
    password: str | None = typer.Option(None, help="Optional password for authenticated smoke checks."),
) -> None:
    asyncio.run(_smoke(base_url=base_url, username=username, password=password))


async def _import_legacy(sql_path: Path, report_dir: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    dataset = parse_legacy_sql(sql_text)
    bundle = build_migration_bundle(dataset)
    summary_path, password_path = write_migration_reports(bundle, report_dir)

    async with AsyncSessionLocal() as session:
        result = await apply_migration(session, bundle)

    typer.echo(
        json.dumps(
            {
                "sql_path": str(sql_path),
                "summary_path": str(summary_path),
                "password_path": str(password_path),
                "result": result,
                "summary": {
                    "users": bundle.summary.total_users,
                    "invites": bundle.summary.total_invites,
                    "accounts": bundle.summary.total_accounts,
                    "study_profiles": bundle.summary.total_study_profiles,
                    "wallets": bundle.summary.total_wallets,
                    "wallet_transactions": bundle.summary.total_wallet_transactions,
                    "accounts_requiring_rebind": bundle.summary.accounts_requiring_rebind,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def _smoke(base_url: str, username: str | None, password: str | None) -> None:
    base_url = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        health_response = await client.get(f"{base_url}/health")
        health_response.raise_for_status()

        payload: dict[str, object] = {
            "health": health_response.json(),
        }

        if username and password:
            login_response = await client.post(
                f"{base_url}/api/v1/auth/login",
                json={"username": username, "password": password},
            )
            login_response.raise_for_status()
            token_payload = login_response.json()
            me_response = await client.get(
                f"{base_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token_payload['access_token']}"},
            )
            me_response.raise_for_status()
            payload["me"] = me_response.json()

        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    app()
