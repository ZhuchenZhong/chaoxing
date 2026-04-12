from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.utils import get_password_hash
from ..core.chaoxing.crypto import AESCipher
from ..models.chaoxing_account import ChaoxingAccount
from ..models.enums import ChaoxingAuthType, NotOpenAction, UserRole
from ..models.invite import Invite
from ..models.study_profile import StudyProfile
from ..models.user import User
from ..models.wallet import Wallet, WalletTransaction


@dataclass(slots=True)
class LegacyUser:
    id: int
    username: str
    display_name: str | None
    password_hash: str
    role: str
    is_super_admin: bool
    is_active: bool
    invited_by_user_id: int | None
    registration_invite_id: int | None
    last_login_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LegacyInvite:
    id: int
    code: str
    note: str | None
    max_uses: int
    bonus_credits: int
    used_count: int
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LegacyAccount:
    id: int
    user_id: int
    display_name: str
    auth_type: str
    username_encrypted: str | None
    password_encrypted: str | None
    cookies_encrypted: str | None
    last_login_ok: bool | None
    last_login_message: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LegacyStudyProfile:
    id: int
    user_id: int
    name: str
    description: str | None
    speed: float
    jobs: int
    notopen_action: str
    tiku_settings: dict[str, Any]
    notification_settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LegacyWallet:
    id: int
    user_id: int
    balance: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LegacyWalletTransaction:
    id: int
    wallet_id: int
    user_id: int
    run_id: int | None
    platform_provider_id: int | None
    provider_name: str | None
    delta: int
    balance_after: int
    reason: str
    metadata_json: dict[str, Any]
    created_at: datetime


@dataclass(slots=True)
class LegacyDataset:
    users: list[LegacyUser]
    invites: list[LegacyInvite]
    accounts: list[LegacyAccount]
    study_profiles: list[LegacyStudyProfile]
    wallets: list[LegacyWallet]
    wallet_transactions: list[LegacyWalletTransaction]


@dataclass(slots=True)
class PasswordRecord:
    user_id: int
    username: str
    display_name: str | None
    initial_password: str


@dataclass(slots=True)
class MigratedUser:
    id: int
    email: str
    username: str
    display_name: str | None
    password_hash: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    invited_by_user_id: int | None
    invite_code_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MigratedInvite:
    id: int
    code: str
    created_by_user_id: int | None
    max_uses: int
    used_count: int
    bonus_credits: int
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


@dataclass(slots=True)
class MigratedAccount:
    id: int
    user_id: int
    display_name: str
    auth_type: ChaoxingAuthType
    username_encrypted: str | None
    password_encrypted: str | None
    cookies_encrypted: str | None
    is_login_valid: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime
    requires_rebind: bool


@dataclass(slots=True)
class MigratedStudyProfile:
    id: int
    user_id: int
    name: str
    speed: Decimal
    notopen_action: NotOpenAction
    tiku_config: dict[str, Any]
    submit_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MigratedWallet:
    id: int
    user_id: int
    balance: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MigratedWalletTransaction:
    id: int
    wallet_id: int
    user_id: int
    related_run_id: int | None
    delta: int
    balance_after: int
    reason: str
    metadata_json: dict[str, Any]
    created_at: datetime


@dataclass(slots=True)
class MigrationSummary:
    total_users: int
    total_invites: int
    total_accounts: int
    total_study_profiles: int
    total_wallets: int
    total_wallet_transactions: int
    accounts_requiring_rebind: int
    reusable_accounts: int


@dataclass(slots=True)
class MigrationBundle:
    users: dict[int, MigratedUser]
    invites: list[MigratedInvite]
    accounts: list[MigratedAccount]
    study_profiles: list[MigratedStudyProfile]
    wallets: list[MigratedWallet]
    wallet_transactions: list[MigratedWalletTransaction]
    password_records: dict[int, PasswordRecord]
    summary: MigrationSummary


def parse_legacy_sql(sql_text: str) -> LegacyDataset:
    users: list[LegacyUser] = []
    invites: list[LegacyInvite] = []
    accounts: list[LegacyAccount] = []
    study_profiles: list[LegacyStudyProfile] = []
    wallets: list[LegacyWallet] = []
    wallet_transactions: list[LegacyWalletTransaction] = []

    for raw_line in sql_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("INSERT INTO public.") or " VALUES " not in line:
            continue

        table_name = line[len("INSERT INTO public.") :].split(" VALUES ", maxsplit=1)[0]
        values_sql = line.split(" VALUES ", maxsplit=1)[1]
        if not values_sql.startswith("(") or not values_sql.endswith(");"):
            continue
        values = _parse_sql_values(values_sql[1:-2])

        if table_name == "users":
            users.append(
                LegacyUser(
                    id=values[0],
                    username=values[1],
                    display_name=values[2],
                    password_hash=values[3],
                    role=values[4],
                    is_super_admin=values[5],
                    is_active=values[6],
                    invited_by_user_id=values[7],
                    registration_invite_id=values[8],
                    last_login_at=_parse_datetime(values[9]),
                    last_seen_at=_parse_datetime(values[10]),
                    created_at=_parse_datetime(values[11], required=True),
                    updated_at=_parse_datetime(values[12], required=True),
                )
            )
        elif table_name == "registration_invites":
            invites.append(
                LegacyInvite(
                    id=values[0],
                    code=values[1],
                    note=values[2],
                    max_uses=values[3],
                    bonus_credits=values[4],
                    used_count=values[5],
                    is_active=values[6],
                    expires_at=_parse_datetime(values[7]),
                    last_used_at=_parse_datetime(values[8]),
                    created_by_user_id=values[9],
                    created_at=_parse_datetime(values[10], required=True),
                    updated_at=_parse_datetime(values[11], required=True),
                )
            )
        elif table_name == "chaoxing_accounts":
            accounts.append(
                LegacyAccount(
                    id=values[0],
                    user_id=values[1],
                    display_name=values[2],
                    auth_type=values[3],
                    username_encrypted=values[4],
                    password_encrypted=values[5],
                    cookies_encrypted=values[6],
                    last_login_ok=values[7],
                    last_login_message=values[8],
                    last_synced_at=_parse_datetime(values[9]),
                    created_at=_parse_datetime(values[10], required=True),
                    updated_at=_parse_datetime(values[11], required=True),
                )
            )
        elif table_name == "study_profiles":
            study_profiles.append(
                LegacyStudyProfile(
                    id=values[0],
                    user_id=values[1],
                    name=values[2],
                    description=values[3],
                    speed=float(values[4]),
                    jobs=values[5],
                    notopen_action=values[6],
                    tiku_settings=_parse_json_object(values[7]),
                    notification_settings=_parse_json_object(values[8]),
                    created_at=_parse_datetime(values[9], required=True),
                    updated_at=_parse_datetime(values[10], required=True),
                )
            )
        elif table_name == "wallets":
            wallets.append(
                LegacyWallet(
                    id=values[0],
                    user_id=values[1],
                    balance=values[2],
                    created_at=_parse_datetime(values[3], required=True),
                    updated_at=_parse_datetime(values[4], required=True),
                )
            )
        elif table_name == "wallet_transactions":
            wallet_transactions.append(
                LegacyWalletTransaction(
                    id=values[0],
                    wallet_id=values[1],
                    user_id=values[2],
                    run_id=values[3],
                    platform_provider_id=values[4],
                    provider_name=values[5],
                    delta=values[6],
                    balance_after=values[7],
                    reason=values[8],
                    metadata_json=_parse_json_object(values[9]),
                    created_at=_parse_datetime(values[10], required=True),
                )
            )

    return LegacyDataset(
        users=users,
        invites=invites,
        accounts=accounts,
        study_profiles=study_profiles,
        wallets=wallets,
        wallet_transactions=wallet_transactions,
    )


def build_migration_bundle(dataset: LegacyDataset) -> MigrationBundle:
    migrated_users: dict[int, MigratedUser] = {}
    password_records: dict[int, PasswordRecord] = {}

    for legacy_user in dataset.users:
        initial_password = _generate_initial_password(legacy_user)
        password_records[legacy_user.id] = PasswordRecord(
            user_id=legacy_user.id,
            username=legacy_user.username,
            display_name=legacy_user.display_name,
            initial_password=initial_password,
        )
        migrated_users[legacy_user.id] = MigratedUser(
            id=legacy_user.id,
            email=_build_placeholder_email(legacy_user.id),
            username=legacy_user.username,
            display_name=legacy_user.display_name,
            password_hash=get_password_hash(initial_password),
            role=_map_user_role(legacy_user.role, legacy_user.is_super_admin),
            is_active=legacy_user.is_active,
            must_change_password=True,
            invited_by_user_id=legacy_user.invited_by_user_id,
            invite_code_id=legacy_user.registration_invite_id,
            created_at=legacy_user.created_at,
            updated_at=legacy_user.updated_at,
        )

    migrated_invites = [
        MigratedInvite(
            id=legacy_invite.id,
            code=legacy_invite.code,
            created_by_user_id=legacy_invite.created_by_user_id,
            max_uses=legacy_invite.max_uses,
            used_count=legacy_invite.used_count,
            bonus_credits=legacy_invite.bonus_credits,
            is_active=legacy_invite.is_active,
            expires_at=legacy_invite.expires_at,
            created_at=legacy_invite.created_at,
        )
        for legacy_invite in dataset.invites
    ]

    migrated_accounts: list[MigratedAccount] = []
    accounts_requiring_rebind = 0
    for legacy_account in dataset.accounts:
        account = _map_account(legacy_account)
        migrated_accounts.append(account)
        if account.requires_rebind:
            accounts_requiring_rebind += 1

    migrated_profiles = [
        MigratedStudyProfile(
            id=legacy_profile.id,
            user_id=legacy_profile.user_id,
            name=_normalize_profile_name(legacy_profile.name),
            speed=Decimal(str(legacy_profile.speed)),
            notopen_action=NotOpenAction(legacy_profile.notopen_action.lower()),
            tiku_config=legacy_profile.tiku_settings,
            submit_config=_build_submit_config(legacy_profile.notification_settings),
            created_at=legacy_profile.created_at,
            updated_at=legacy_profile.updated_at,
        )
        for legacy_profile in dataset.study_profiles
    ]

    migrated_wallets = [
        MigratedWallet(
            id=legacy_wallet.id,
            user_id=legacy_wallet.user_id,
            balance=legacy_wallet.balance,
            created_at=legacy_wallet.created_at,
            updated_at=legacy_wallet.updated_at,
        )
        for legacy_wallet in dataset.wallets
    ]

    migrated_transactions = [
        MigratedWalletTransaction(
            id=legacy_tx.id,
            wallet_id=legacy_tx.wallet_id,
            user_id=legacy_tx.user_id,
            related_run_id=None,
            delta=legacy_tx.delta,
            balance_after=legacy_tx.balance_after,
            reason=legacy_tx.reason,
            metadata_json=_build_transaction_metadata(legacy_tx),
            created_at=legacy_tx.created_at,
        )
        for legacy_tx in dataset.wallet_transactions
    ]

    summary = MigrationSummary(
        total_users=len(migrated_users),
        total_invites=len(migrated_invites),
        total_accounts=len(migrated_accounts),
        total_study_profiles=len(migrated_profiles),
        total_wallets=len(migrated_wallets),
        total_wallet_transactions=len(migrated_transactions),
        accounts_requiring_rebind=accounts_requiring_rebind,
        reusable_accounts=len(migrated_accounts) - accounts_requiring_rebind,
    )
    return MigrationBundle(
        users=migrated_users,
        invites=migrated_invites,
        accounts=migrated_accounts,
        study_profiles=migrated_profiles,
        wallets=migrated_wallets,
        wallet_transactions=migrated_transactions,
        password_records=password_records,
        summary=summary,
    )


async def apply_migration(session: AsyncSession, bundle: MigrationBundle) -> dict[str, int]:
    for migrated_user in bundle.users.values():
        user = await session.get(User, migrated_user.id)
        if user is None:
            user = User(
                id=migrated_user.id,
                email=migrated_user.email,
                username=migrated_user.username,
                display_name=migrated_user.display_name,
                password_hash=migrated_user.password_hash,
                role=migrated_user.role,
                is_active=migrated_user.is_active,
                must_change_password=migrated_user.must_change_password,
                invited_by_user_id=None,
                invite_code_id=None,
                created_at=migrated_user.created_at,
                updated_at=migrated_user.updated_at,
            )
            session.add(user)
        else:
            user.email = migrated_user.email
            user.username = migrated_user.username
            user.display_name = migrated_user.display_name
            user.password_hash = migrated_user.password_hash
            user.role = migrated_user.role
            user.is_active = migrated_user.is_active
            user.must_change_password = migrated_user.must_change_password
            user.created_at = migrated_user.created_at
            user.updated_at = migrated_user.updated_at
            user.invited_by_user_id = None
            user.invite_code_id = None

    await session.flush()

    for migrated_invite in bundle.invites:
        invite = await session.get(Invite, migrated_invite.id)
        if invite is None:
            invite = Invite(
                id=migrated_invite.id,
                code=migrated_invite.code,
                created_by_user_id=migrated_invite.created_by_user_id,
                max_uses=migrated_invite.max_uses,
                used_count=migrated_invite.used_count,
                bonus_credits=migrated_invite.bonus_credits,
                is_active=migrated_invite.is_active,
                expires_at=migrated_invite.expires_at,
                created_at=migrated_invite.created_at,
            )
            session.add(invite)
        else:
            invite.code = migrated_invite.code
            invite.created_by_user_id = migrated_invite.created_by_user_id
            invite.max_uses = migrated_invite.max_uses
            invite.used_count = migrated_invite.used_count
            invite.bonus_credits = migrated_invite.bonus_credits
            invite.is_active = migrated_invite.is_active
            invite.expires_at = migrated_invite.expires_at
            invite.created_at = migrated_invite.created_at

    await session.flush()

    for migrated_user in bundle.users.values():
        user = await session.get(User, migrated_user.id)
        if user is None:
            continue
        user.invited_by_user_id = migrated_user.invited_by_user_id
        user.invite_code_id = migrated_user.invite_code_id

    for migrated_account in bundle.accounts:
        account = await session.get(ChaoxingAccount, migrated_account.id)
        if account is None:
            account = ChaoxingAccount(
                id=migrated_account.id,
                user_id=migrated_account.user_id,
                display_name=migrated_account.display_name,
                auth_type=migrated_account.auth_type,
                username_encrypted=migrated_account.username_encrypted,
                password_encrypted=migrated_account.password_encrypted,
                cookies_encrypted=migrated_account.cookies_encrypted,
                is_login_valid=migrated_account.is_login_valid,
                last_synced_at=migrated_account.last_synced_at,
                created_at=migrated_account.created_at,
                updated_at=migrated_account.updated_at,
            )
            session.add(account)
        else:
            account.user_id = migrated_account.user_id
            account.display_name = migrated_account.display_name
            account.auth_type = migrated_account.auth_type
            account.username_encrypted = migrated_account.username_encrypted
            account.password_encrypted = migrated_account.password_encrypted
            account.cookies_encrypted = migrated_account.cookies_encrypted
            account.is_login_valid = migrated_account.is_login_valid
            account.last_synced_at = migrated_account.last_synced_at
            account.created_at = migrated_account.created_at
            account.updated_at = migrated_account.updated_at

    for migrated_profile in bundle.study_profiles:
        profile = await session.get(StudyProfile, migrated_profile.id)
        if profile is None:
            profile = StudyProfile(
                id=migrated_profile.id,
                user_id=migrated_profile.user_id,
                name=migrated_profile.name,
                speed=migrated_profile.speed,
                notopen_action=migrated_profile.notopen_action,
                tiku_config=migrated_profile.tiku_config,
                submit_config=migrated_profile.submit_config,
                created_at=migrated_profile.created_at,
                updated_at=migrated_profile.updated_at,
            )
            session.add(profile)
        else:
            profile.user_id = migrated_profile.user_id
            profile.name = migrated_profile.name
            profile.speed = migrated_profile.speed
            profile.notopen_action = migrated_profile.notopen_action
            profile.tiku_config = migrated_profile.tiku_config
            profile.submit_config = migrated_profile.submit_config
            profile.created_at = migrated_profile.created_at
            profile.updated_at = migrated_profile.updated_at

    for migrated_wallet in bundle.wallets:
        wallet = await session.get(Wallet, migrated_wallet.id)
        if wallet is None:
            wallet = Wallet(
                id=migrated_wallet.id,
                user_id=migrated_wallet.user_id,
                balance=migrated_wallet.balance,
                created_at=migrated_wallet.created_at,
                updated_at=migrated_wallet.updated_at,
            )
            session.add(wallet)
        else:
            wallet.user_id = migrated_wallet.user_id
            wallet.balance = migrated_wallet.balance
            wallet.created_at = migrated_wallet.created_at
            wallet.updated_at = migrated_wallet.updated_at

    await session.flush()

    for migrated_tx in bundle.wallet_transactions:
        transaction = await session.get(WalletTransaction, migrated_tx.id)
        if transaction is None:
            transaction = WalletTransaction(
                id=migrated_tx.id,
                wallet_id=migrated_tx.wallet_id,
                user_id=migrated_tx.user_id,
                related_run_id=migrated_tx.related_run_id,
                delta=migrated_tx.delta,
                balance_after=migrated_tx.balance_after,
                reason=migrated_tx.reason,
                metadata_json=migrated_tx.metadata_json,
                created_at=migrated_tx.created_at,
            )
            session.add(transaction)
        else:
            transaction.wallet_id = migrated_tx.wallet_id
            transaction.user_id = migrated_tx.user_id
            transaction.related_run_id = migrated_tx.related_run_id
            transaction.delta = migrated_tx.delta
            transaction.balance_after = migrated_tx.balance_after
            transaction.reason = migrated_tx.reason
            transaction.metadata_json = migrated_tx.metadata_json
            transaction.created_at = migrated_tx.created_at

    await session.commit()
    return {
        "users_upserted": bundle.summary.total_users,
        "invites_upserted": bundle.summary.total_invites,
        "accounts_upserted": bundle.summary.total_accounts,
        "study_profiles_upserted": bundle.summary.total_study_profiles,
        "wallets_upserted": bundle.summary.total_wallets,
        "wallet_transactions_upserted": bundle.summary.total_wallet_transactions,
    }


def write_migration_reports(bundle: MigrationBundle, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "legacy-migration-summary.json"
    password_path = output_dir / "legacy-initial-passwords.csv"

    summary_payload = {
        **asdict(bundle.summary),
        "accounts": [
            {
                "id": account.id,
                "user_id": account.user_id,
                "display_name": account.display_name,
                "auth_type": account.auth_type.value,
                "requires_rebind": account.requires_rebind,
            }
            for account in bundle.accounts
        ],
    }
    summary_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["user_id,username,display_name,initial_password"]
    for user_id in sorted(bundle.password_records):
        record = bundle.password_records[user_id]
        display_name = "" if record.display_name is None else record.display_name.replace(",", " ")
        lines.append(
            f"{record.user_id},{record.username},{display_name},{record.initial_password}"
        )
    password_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, password_path


def _map_account(legacy_account: LegacyAccount) -> MigratedAccount:
    auth_type = ChaoxingAuthType(legacy_account.auth_type.lower())
    requires_rebind = False
    username_encrypted = legacy_account.username_encrypted
    password_encrypted = legacy_account.password_encrypted
    cookies_encrypted = legacy_account.cookies_encrypted

    if auth_type == ChaoxingAuthType.PASSWORD:
        if not (_can_reuse_ciphertext(username_encrypted) and _can_reuse_ciphertext(password_encrypted)):
            username_encrypted = None
            password_encrypted = None
            requires_rebind = True
    elif auth_type == ChaoxingAuthType.COOKIES and not _can_reuse_ciphertext(cookies_encrypted):
        cookies_encrypted = None
        requires_rebind = True

    return MigratedAccount(
        id=legacy_account.id,
        user_id=legacy_account.user_id,
        display_name=legacy_account.display_name,
        auth_type=auth_type,
        username_encrypted=username_encrypted,
        password_encrypted=password_encrypted,
        cookies_encrypted=cookies_encrypted,
        is_login_valid=bool(legacy_account.last_login_ok) and not requires_rebind,
        last_synced_at=legacy_account.last_synced_at,
        created_at=legacy_account.created_at,
        updated_at=legacy_account.updated_at,
        requires_rebind=requires_rebind,
    )


def _build_placeholder_email(user_id: int) -> str:
    return f"legacy-user-{user_id}@migrated.local"


def _generate_initial_password(legacy_user: LegacyUser) -> str:
    digest = hashlib.sha256(
        f"{legacy_user.id}:{legacy_user.username}:{legacy_user.created_at.isoformat()}".encode(
            "utf-8"
        )
    ).hexdigest()[:10]
    return f"Cx{legacy_user.id}!{digest}"


def _map_user_role(role: str, is_super_admin: bool) -> UserRole:
    if is_super_admin or role.lower() == "admin":
        return UserRole.ADMIN
    return UserRole.USER


def _build_submit_config(notification_settings: dict[str, Any]) -> dict[str, Any]:
    if not notification_settings:
        return {}
    return {"legacy_notification_settings": notification_settings}


def _build_transaction_metadata(
    legacy_tx: LegacyWalletTransaction,
) -> dict[str, Any]:
    metadata = dict(legacy_tx.metadata_json)
    if legacy_tx.run_id is not None:
        metadata["legacyRunId"] = legacy_tx.run_id
    if legacy_tx.platform_provider_id is not None:
        metadata["legacyPlatformProviderId"] = legacy_tx.platform_provider_id
    if legacy_tx.provider_name is not None:
        metadata["legacyProviderName"] = legacy_tx.provider_name
    return metadata


def _normalize_profile_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in {"default", "默认配置"} or "默认" in name:
        return "default"
    return name.strip()


def _can_reuse_ciphertext(value: str | None) -> bool:
    if value is None:
        return False
    cipher = AESCipher()
    try:
        cipher.decrypt(value)
    except Exception:
        return False
    return True


def _parse_sql_values(values_sql: str) -> list[Any]:
    values: list[Any] = []
    buffer: list[str] = []
    in_string = False
    token_quoted = False
    index = 0

    while index < len(values_sql):
        char = values_sql[index]
        if in_string:
            if char == "'":
                if index + 1 < len(values_sql) and values_sql[index + 1] == "'":
                    buffer.append("'")
                    index += 2
                    continue
                in_string = False
                index += 1
                continue
            buffer.append(char)
            index += 1
            continue

        if char == "'":
            in_string = True
            token_quoted = True
            index += 1
            continue
        if char == ",":
            values.append(_coerce_sql_token("".join(buffer).strip(), token_quoted))
            buffer = []
            token_quoted = False
            index += 1
            continue

        buffer.append(char)
        index += 1

    values.append(_coerce_sql_token("".join(buffer).strip(), token_quoted))
    return values


def _coerce_sql_token(raw_token: str, quoted: bool) -> Any:
    if quoted:
        return raw_token
    if raw_token == "NULL":
        return None
    if raw_token == "true":
        return True
    if raw_token == "false":
        return False
    if raw_token.lstrip("-").isdigit():
        return int(raw_token)
    try:
        return float(raw_token)
    except ValueError:
        return raw_token


def _parse_datetime(value: Any, *, required: bool = False) -> datetime | None:
    if value is None:
        if required:
            raise ValueError("Required datetime value is missing")
        return None
    return datetime.fromisoformat(value)


def _parse_json_object(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("Expected JSON object payload")
