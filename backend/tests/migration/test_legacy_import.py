from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chaoxing.db.database import Base
from chaoxing.models.chaoxing_account import ChaoxingAccount
from chaoxing.models.invite import Invite
from chaoxing.models.study_profile import StudyProfile
from chaoxing.models.user import User
from chaoxing.models.wallet import Wallet, WalletTransaction


SAMPLE_SQL = """
INSERT INTO public.users VALUES (1, 'admin', 'Admin', 'legacy-hash-admin', 'ADMIN', true, true, NULL, NULL, '2026-03-24 16:20:16.810988+00', '2026-03-24 16:20:16.810988+00', '2026-03-22 14:46:41.395066+00', '2026-03-24 16:20:16.714649+00');
INSERT INTO public.users VALUES (2, 'alice', 'Alice', 'legacy-hash-user', 'USER', false, true, 1, 10, NULL, NULL, '2026-03-23 00:29:22.608186+00', '2026-03-23 00:29:22.608186+00');
INSERT INTO public.registration_invites VALUES (10, 'INV-LEGACY', 'legacy note', 5, 300, 1, true, NULL, '2026-03-24 16:20:16.810988+00', 1, '2026-03-22 15:24:34.202141+00', '2026-03-23 00:29:22.608186+00');
INSERT INTO public.chaoxing_accounts VALUES (7, 2, 'main', 'PASSWORD', 'gAAAAABlegacy-user', 'gAAAAABlegacy-pass', NULL, true, '登录成功', '2026-03-24 16:20:16.810988+00', '2026-03-22 15:26:14.071684+00', '2026-03-24 16:20:16.714649+00');
INSERT INTO public.study_profiles VALUES (5, 2, '默认配置', NULL, 1.5, 4, 'continue', '{"provider":"openai_compat"}', '{"channel":"serverchan"}', '2026-03-22 15:25:59.57604+00', '2026-03-22 15:25:59.57604+00');
INSERT INTO public.wallets VALUES (12, 2, 900, '2026-03-22 15:25:59.57604+00', '2026-03-22 17:27:02.927282+00');
INSERT INTO public.wallet_transactions VALUES (31, 12, 2, 9, 3, 'AI', -5, 895, 'provider_request', '{"questionTitle":"q1"}', '2026-03-24 16:20:16.810988+00');
"""


def test_parse_legacy_sql_extracts_supported_tables():
    from chaoxing.migration.legacy_import import parse_legacy_sql

    dataset = parse_legacy_sql(SAMPLE_SQL)

    assert len(dataset.users) == 2
    assert dataset.users[1].username == "alice"
    assert dataset.users[1].registration_invite_id == 10
    assert len(dataset.invites) == 1
    assert dataset.invites[0].code == "INV-LEGACY"
    assert len(dataset.accounts) == 1
    assert dataset.accounts[0].last_login_ok is True
    assert len(dataset.wallet_transactions) == 1
    assert dataset.wallet_transactions[0].provider_name == "AI"


def test_build_migration_bundle_maps_records_and_flags_rebinds():
    from chaoxing.migration.legacy_import import build_migration_bundle, parse_legacy_sql

    bundle = build_migration_bundle(parse_legacy_sql(SAMPLE_SQL))

    assert bundle.summary.total_users == 2
    assert bundle.summary.accounts_requiring_rebind == 1
    migrated_user = bundle.users[2]
    assert migrated_user.email == "legacy-user-2@migrated.local"
    assert migrated_user.must_change_password is True
    assert migrated_user.invited_by_user_id == 1
    assert migrated_user.invite_code_id == 10

    migrated_account = bundle.accounts[0]
    assert migrated_account.id == 7
    assert migrated_account.username_encrypted is None
    assert migrated_account.password_encrypted is None
    assert migrated_account.requires_rebind is True
    assert migrated_account.is_login_valid is False

    migrated_profile = bundle.study_profiles[0]
    assert migrated_profile.name == "default"
    assert migrated_profile.tiku_config["provider"] == "openai_compat"
    assert migrated_profile.submit_config["legacy_notification_settings"]["channel"] == "serverchan"

    migrated_tx = bundle.wallet_transactions[0]
    assert migrated_tx.related_run_id is None
    assert migrated_tx.metadata_json["legacyRunId"] == 9
    assert migrated_tx.metadata_json["legacyPlatformProviderId"] == 3
    assert migrated_tx.metadata_json["legacyProviderName"] == "AI"

    password_record = bundle.password_records[2]
    assert password_record.user_id == 2
    assert password_record.initial_password.startswith("Cx2!")


@pytest.mark.asyncio
async def test_apply_migration_is_idempotent_and_preserves_relations(tmp_path: Path):
    from chaoxing.migration.legacy_import import (
        apply_migration,
        build_migration_bundle,
        parse_legacy_sql,
        write_migration_reports,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bundle = build_migration_bundle(parse_legacy_sql(SAMPLE_SQL))

    async with session_factory() as session:
        first_report = await apply_migration(session, bundle)
        second_report = await apply_migration(session, bundle)

        users = list((await session.execute(select(User).order_by(User.id.asc()))).scalars().all())
        invites = list((await session.execute(select(Invite))).scalars().all())
        accounts = list((await session.execute(select(ChaoxingAccount))).scalars().all())
        profiles = list((await session.execute(select(StudyProfile))).scalars().all())
        wallets = list((await session.execute(select(Wallet))).scalars().all())
        transactions = list(
            (await session.execute(select(WalletTransaction).order_by(WalletTransaction.id.asc())))
            .scalars()
            .all()
        )

    assert first_report["users_upserted"] == 2
    assert second_report["users_upserted"] == 2
    assert len(users) == 2
    assert len(invites) == 1
    assert len(accounts) == 1
    assert len(profiles) == 1
    assert len(wallets) == 1
    assert len(transactions) == 1

    assert users[1].email == "legacy-user-2@migrated.local"
    assert users[1].invite_code_id == 10
    assert users[1].must_change_password is True
    assert invites[0].created_by_user_id == 1
    assert accounts[0].id == 7
    assert accounts[0].user_id == 2
    assert accounts[0].username_encrypted is None
    assert wallets[0].id == 12
    assert wallets[0].balance == 900
    assert transactions[0].related_run_id is None
    assert transactions[0].metadata_json["legacyRunId"] == 9
    assert transactions[0].metadata_json["legacyProviderName"] == "AI"
    assert profiles[0].name == "default"

    summary_path, password_path = write_migration_reports(bundle, tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    password_lines = password_path.read_text(encoding="utf-8").splitlines()

    assert summary["accounts_requiring_rebind"] == 1
    assert password_lines[0] == "user_id,username,display_name,initial_password"
    assert "2,alice,Alice," in password_lines[2]

    await engine.dispose()
