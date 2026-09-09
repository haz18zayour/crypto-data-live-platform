from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.errors import CheckViolation

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


@pytest.fixture(scope="session", autouse=True)
def migrated_postgres() -> Iterator[tuple[psycopg.Connection, str]]:
    schema = f"test_migration_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL migration tests could not connect; check TEST_DATABASE_URL, "
            "DATABASE_URL, or DATABASE_URL in .env.local"
        ) from None

    with connection:
        with connection.transaction():
            connection.execute(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                  END IF;
                  IF NOT EXISTS (
                    SELECT FROM pg_roles WHERE rolname = 'authenticated'
                  ) THEN
                    CREATE ROLE authenticated NOLOGIN;
                  END IF;
                END
                $$;
                """
            )
            connection.execute(
                sql.SQL("create schema {}").format(sql.Identifier(schema))
            )
            connection.execute(
                sql.SQL("set local search_path to {}").format(sql.Identifier(schema))
            )

            migration_files = sorted(MIGRATIONS.glob("*.sql"))
            assert migration_files, "at least one SQL migration must exist"
            for migration in migration_files:
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{sql.Identifier(schema).as_string(connection)}."
                )
                connection.execute(migration_sql)

        try:
            yield connection, schema
        finally:
            with connection.transaction():
                connection.execute(
                    sql.SQL("drop schema if exists {} cascade").format(
                        sql.Identifier(schema)
                    )
                )


def _insert(
    *,
    connection: psycopg.Connection,
    schema: str,
    indicator_key: str,
    asset: str = "BTC",
    measured_on: str = "BTC",
    value: float | None = 42000.0,
    status: str = "OK",
    reason: str | None = None,
) -> None:
    connection.execute(
        sql.SQL(
            """
            insert into {}.datapoints (
              indicator_key, asset, measured_on, value, status, reason,
              source_vendor, endpoint, source_field, fetched_at, source_timestamp
            ) values (
              %s, %s, %s, %s, %s, %s,
              'okx', 'https://www.okx.com/api/v5/market/candles',
              'candle[4] where candle[8] = 1', now(), now()
            )
            """
        ).format(sql.Identifier(schema)),
        (indicator_key, asset, measured_on, value, status, reason),
    )


def test_asset_match_rejects_ok_row_measured_on_another_asset(
    migrated_postgres: tuple[psycopg.Connection, str],
) -> None:
    connection, schema = migrated_postgres
    with (
        pytest.raises(CheckViolation, match="asset_match"),
        connection.transaction(),
    ):
        _insert(
            connection=connection,
            schema=schema,
            indicator_key="asset_match_bad",
            asset="SOL",
            measured_on="BTC",
        )

    with connection.transaction():
        _insert(
            connection=connection,
            schema=schema,
            indicator_key="asset_match_good",
            asset="SOL",
            measured_on="BTC",
            value=None,
            status="UNAVAILABLE",
            reason="NOT_DEFINABLE",
        )


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
            None,
            "OK",
            None,
            42000.0,
            "OK",
            None,
        ),
        (
            "value_iff_ok_present",
            42000.0,
            "UNAVAILABLE",
            "FETCH_FAILED",
            None,
            "UNAVAILABLE",
            "FETCH_FAILED",
        ),
    ),
)
def test_value_iff_ok_rejects_status_and_value_drift(
    migrated_postgres: tuple[psycopg.Connection, str],
    indicator_key: str,
    value: float | None,
    status: str,
    reason: str | None,
    accepted_value: float | None,
    accepted_status: str,
    accepted_reason: str | None,
) -> None:
    connection, schema = migrated_postgres
    with (
        pytest.raises(CheckViolation, match="value_iff_ok"),
        connection.transaction(),
    ):
        _insert(
            connection=connection,
            schema=schema,
            indicator_key=indicator_key,
            value=value,
            status=status,
            reason=reason,
        )

    with connection.transaction():
        _insert(
            connection=connection,
            schema=schema,
            indicator_key=f"{indicator_key}_good",
            value=accepted_value,
            status=accepted_status,
            reason=accepted_reason,
        )


def test_reason_required_rejects_unavailable_without_reason(
    migrated_postgres: tuple[psycopg.Connection, str],
) -> None:
    connection, schema = migrated_postgres
    with (
        pytest.raises(CheckViolation, match="reason_required"),
        connection.transaction(),
    ):
        _insert(
            connection=connection,
            schema=schema,
            indicator_key="reason_required_bad",
            value=None,
            status="UNAVAILABLE",
        )

    with connection.transaction():
        _insert(
            connection=connection,
            schema=schema,
            indicator_key="reason_required_good",
            value=None,
            status="UNAVAILABLE",
            reason="FETCH_FAILED",
        )
