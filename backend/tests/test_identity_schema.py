import chaoxing.models  # noqa: F401
from chaoxing.db.database import Base
from chaoxing.models.user import User


def test_metadata_bootstraps_cleanly():
    table_names = set(Base.metadata.tables)
    assert "users" in table_names
    assert "invites" in table_names
    assert "chaoxing_accounts" in table_names
    assert "study_profiles" in table_names
    assert "wallets" in table_names
    assert "wallet_transactions" in table_names
    assert "study_runs" in table_names
    assert "study_run_events" in table_names
    assert "credit_packages" in table_names
    assert "recharge_orders" in table_names
    assert "tiku_providers" in table_names
    assert "tiku_cache_entries" in table_names
    assert "system_settings" in table_names


def test_user_columns_match_identity_contract():
    columns = User.__table__.c
    assert "display_name" in columns
    assert "invited_by_user_id" in columns
    assert "invite_code_id" in columns
    assert "email" in columns
    assert "must_change_password" in columns


def test_user_relationships_cover_accounts_profiles_and_invites():
    names = set(User.__mapper__.relationships.keys())
    assert "chaoxing_accounts" in names
    assert "study_profiles" in names
    assert "created_invites" in names
    assert "wallet" in names
