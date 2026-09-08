from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


def _psql(sql: str) -> subprocess.CompletedProcess[str]:
    container = os.environ.get("TEST_POSTGRES_CONTAINER")
    if container:
        command = [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "app",
            "-X",
            "--set",
            "ON_ERROR_STOP=1",
        ]
    else:
        command = [
            "psql",
            os.environ["TEST_DATABASE_URL"],
            "-X",
            "--set",
            "ON_ERROR_STOP=1",
        ]
    return subprocess.run(
        command,
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture(scope="session", autouse=True)
def migrated_postgres() -> None:
    if "TEST_DATABASE_URL" not in os.environ:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    roles = _psql(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
            CREATE ROLE anon NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated NOLOGIN;
          END IF;
        END
        $$;
        """
    )
    assert roles.returncode == 0, roles.stderr

    migration_files = sorted(MIGRATIONS.glob("*.sql"))
    assert migration_files, "at least one SQL migration must exist"
    for migration in migration_files:
        applied = _psql(migration.read_text(encoding="utf-8"))
        assert applied.returncode == 0, applied.stderr


def _insert(
    *,
    indicator_key: str,
    asset: str = "BTC",
    measured_on: str = "BTC",
    value: str = "42000.0",
    status: str = "OK",
    reason: str = "NULL",
) -> subprocess.CompletedProcess[str]:
    return _psql(
        f"""
        INSERT INTO datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp
        ) VALUES (
          '{indicator_key}', '{asset}', '{measured_on}', {value}, '{status}', {reason},
          'okx', 'https://www.okx.com/api/v5/market/candles',
          'candle[4] where candle[8] = 1', now(), now()
        );
        """
    )


def test_asset_match_rejects_ok_row_measured_on_another_asset() -> None:
    rejected = _insert(
        indicator_key="asset_match_bad",
        asset="SOL",
        measured_on="BTC",
    )
    assert rejected.returncode != 0
    assert "asset_match" in rejected.stderr

    accepted = _insert(
        indicator_key="asset_match_good",
        asset="SOL",
        measured_on="BTC",
        value="NULL",
        status="UNAVAILABLE",
        reason="'NOT_DEFINABLE'",
    )
    assert accepted.returncode == 0, accepted.stderr


@pytest.mark.parametrize(
    ("indicator_key", "value", "status", "reason"),
    (
        ("value_iff_ok_missing", "NULL", "OK", "NULL"),
        ("value_iff_ok_present", "42000.0", "UNAVAILABLE", "'FETCH_FAILED'"),
    ),
)
def test_value_iff_ok_rejects_status_and_value_drift(
    indicator_key: str,
    value: str,
    status: str,
    reason: str,
) -> None:
    rejected = _insert(
        indicator_key=indicator_key,
        value=value,
        status=status,
        reason=reason,
    )
    assert rejected.returncode != 0
    assert "value_iff_ok" in rejected.stderr

    accepted = _insert(indicator_key=f"{indicator_key}_good")
    assert accepted.returncode == 0, accepted.stderr


def test_reason_required_rejects_unavailable_without_reason() -> None:
    rejected = _insert(
        indicator_key="reason_required_bad",
        value="NULL",
        status="UNAVAILABLE",
    )
    assert rejected.returncode != 0
    assert "reason_required" in rejected.stderr

    accepted = _insert(
        indicator_key="reason_required_good",
        value="NULL",
        status="UNAVAILABLE",
        reason="'FETCH_FAILED'",
    )
    assert accepted.returncode == 0, accepted.stderr
