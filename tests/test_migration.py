from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip("'\"")

    raise RuntimeError(
        "PostgreSQL migration tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


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
            _database_url(),
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
def migrated_postgres() -> Iterator[str]:
    if "TEST_POSTGRES_CONTAINER" not in os.environ:
        _database_url()

    schema = f"test_migration_{uuid4().hex}"
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

    created = _psql(f'create schema "{schema}";')
    assert created.returncode == 0, created.stderr

    try:
        migration_files = sorted(MIGRATIONS.glob("*.sql"))
        assert migration_files, "at least one SQL migration must exist"
        for migration in migration_files:
            sql = migration.read_text(encoding="utf-8").replace(
                "public.", f'"{schema}".'
            )
            applied = _psql(f'set search_path to "{schema}";\n{sql}')
            assert applied.returncode == 0, applied.stderr

        yield schema
    finally:
        dropped = _psql(f'drop schema if exists "{schema}" cascade;')
        assert dropped.returncode == 0, dropped.stderr


def _insert(
    *,
    schema: str,
    indicator_key: str,
    asset: str = "BTC",
    measured_on: str = "BTC",
    value: str = "42000.0",
    status: str = "OK",
    reason: str = "NULL",
) -> subprocess.CompletedProcess[str]:
    return _psql(
        f"""
        SET search_path TO "{schema}";
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


def test_asset_match_rejects_ok_row_measured_on_another_asset(
    migrated_postgres: str,
) -> None:
    rejected = _insert(
        schema=migrated_postgres,
        indicator_key="asset_match_bad",
        asset="SOL",
        measured_on="BTC",
    )
    assert rejected.returncode != 0
    assert "asset_match" in rejected.stderr

    accepted = _insert(
        schema=migrated_postgres,
        indicator_key="asset_match_good",
        asset="SOL",
        measured_on="BTC",
        value="NULL",
        status="UNAVAILABLE",
        reason="'NOT_DEFINABLE'",
    )
    assert accepted.returncode == 0, accepted.stderr


@pytest.mark.parametrize(
    (
        "indicator_key",
        "value",
        "status",
        "reason",
        "accepted_value",
        "accepted_status",
        "accepted_reason",
    ),
    (
        (
            "value_iff_ok_missing",
            "NULL",
            "OK",
            "NULL",
            "42000.0",
            "OK",
            "NULL",
        ),
        (
            "value_iff_ok_present",
            "42000.0",
            "UNAVAILABLE",
            "'FETCH_FAILED'",
            "NULL",
            "UNAVAILABLE",
            "'FETCH_FAILED'",
        ),
    ),
)
def test_value_iff_ok_rejects_status_and_value_drift(
    migrated_postgres: str,
    indicator_key: str,
    value: str,
    status: str,
    reason: str,
    accepted_value: str,
    accepted_status: str,
    accepted_reason: str,
) -> None:
    rejected = _insert(
        schema=migrated_postgres,
        indicator_key=indicator_key,
        value=value,
        status=status,
        reason=reason,
    )
    assert rejected.returncode != 0
    assert "value_iff_ok" in rejected.stderr

    accepted = _insert(
        schema=migrated_postgres,
        indicator_key=f"{indicator_key}_good",
        value=accepted_value,
        status=accepted_status,
        reason=accepted_reason,
    )
    assert accepted.returncode == 0, accepted.stderr


def test_reason_required_rejects_unavailable_without_reason(
    migrated_postgres: str,
) -> None:
    rejected = _insert(
        schema=migrated_postgres,
        indicator_key="reason_required_bad",
        value="NULL",
        status="UNAVAILABLE",
    )
    assert rejected.returncode != 0
    assert "reason_required" in rejected.stderr

    accepted = _insert(
        schema=migrated_postgres,
        indicator_key="reason_required_good",
        value="NULL",
        status="UNAVAILABLE",
        reason="'FETCH_FAILED'",
    )
    assert accepted.returncode == 0, accepted.stderr
