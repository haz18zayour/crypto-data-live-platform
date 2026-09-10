from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from ingest.persist import persist_datapoint
from ingest.registry import IndicatorDefinition
from ingest.status import Ok

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
SOURCE_TIMESTAMP = datetime(2026, 9, 9, tzinfo=UTC)


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
        "PostgreSQL corroboration schema tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[psycopg.Connection[tuple[object, ...]], str]]:
    schema = f"test_corroboration_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL corroboration schema tests could not connect; check "
            "TEST_DATABASE_URL, DATABASE_URL, or DATABASE_URL in .env.local"
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
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{sql.Identifier(schema).as_string(connection)}."
                )
                connection.execute(migration_sql)
        connection.execute(
            sql.SQL("set search_path to {}").format(sql.Identifier(schema))
        )

        try:
            yield connection, schema
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(
                    sql.Identifier(schema)
                )
            )


def _definition(*, key: str, vendor: str) -> IndicatorDefinition:
    return IndicatorDefinition(
        key=key,
        vendor=vendor,
        endpoint=f"https://{vendor}.example.test/candles",
        source_field="close",
        definable_for=("BTC",),
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


def _persist(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    definition: IndicatorDefinition,
    value: float,
) -> int:
    return persist_datapoint(
        connection,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=value, source_timestamp=SOURCE_TIMESTAMP),
    )


def test_two_venues_for_the_same_indicator_and_timestamp_produce_two_rows(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"two_venues_{uuid4().hex}"

    okx_id = _persist(
        connection, definition=_definition(key=key, vendor="okx"), value=79_111.8
    )
    coinbase_id = _persist(
        connection,
        definition=_definition(key=key, vendor="coinbase"),
        value=79_056.2,
    )

    rows = connection.execute(
        """
        select id, source_vendor, value
        from datapoints
        where indicator_key = %s and source_timestamp = %s
        order by source_vendor
        """,
        (key, SOURCE_TIMESTAMP),
    ).fetchall()

    assert okx_id != coinbase_id
    assert rows == [
        (coinbase_id, "coinbase", 79_056.2),
        (okx_id, "okx", 79_111.8),
    ]


def test_rewriting_the_same_venue_and_timestamp_still_upserts(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    definition = _definition(key=f"same_venue_{uuid4().hex}", vendor="okx")

    first_id = _persist(connection, definition=definition, value=79_000.0)
    second_id = _persist(connection, definition=definition, value=79_111.8)
    rows = connection.execute(
        """
        select id, value
        from datapoints
        where indicator_key = %s and source_vendor = %s
          and source_timestamp = %s
        """,
        (definition.key, definition.vendor, SOURCE_TIMESTAMP),
    ).fetchall()

    assert second_id == first_id
    assert rows == [(first_id, 79_111.8)]


def test_a_corroboration_record_stores_divergence_and_tolerance_at_write_time(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"stored_tolerance_{uuid4().hex}"
    datapoint_ids = sorted(
        (
            _persist(
                connection,
                definition=_definition(key=key, vendor="okx"),
                value=79_111.8,
            ),
            _persist(
                connection,
                definition=_definition(key=key, vendor="coinbase"),
                value=79_056.2,
            ),
        )
    )
    tolerance_bps = 25.0

    inserted = connection.execute(
        """
        insert into corroborations (
          datapoint_a_id, datapoint_b_id, divergence_bps,
          tolerance_bps_at_write, status
        ) values (%s, %s, %s, %s, 'CORROBORATED')
        returning id
        """,
        (*datapoint_ids, 7.03, tolerance_bps),
    ).fetchone()
    assert inserted is not None
    corroboration_id = inserted[0]
    tolerance_bps = 30.0

    stored = connection.execute(
        """
        select divergence_bps, tolerance_bps_at_write
        from corroborations
        where id = %s
        """,
        (corroboration_id,),
    ).fetchone()

    assert tolerance_bps == 30.0
    assert stored == (7.03, 25.0)


def test_the_schema_has_no_column_implying_a_primary_or_preferred_venue(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    columns = {
        str(row[0])
        for row in connection.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = %s
              and table_name in ('datapoints', 'corroborations')
            """,
            (schema,),
        ).fetchall()
    }

    assert "value_secondary" not in columns
    assert "is_primary" not in columns
    preference_terms = ("primary", "preferred", "secondary")
    assert not any(
        term in column for column in columns for term in preference_terms
    )


@pytest.mark.integration
def test_migration_applies_to_a_real_postgres_and_both_venues_round_trip(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    key = f"round_trip_{uuid4().hex}"

    _persist(
        connection, definition=_definition(key=key, vendor="okx"), value=79_111.8
    )
    _persist(
        connection,
        definition=_definition(key=key, vendor="coinbase"),
        value=79_056.2,
    )

    rows = connection.execute(
        sql.SQL(
            """
            select source_vendor, value, source_timestamp
            from {}.datapoints
            where indicator_key = %s
            order by source_vendor
            """
        ).format(sql.Identifier(schema)),
        (key,),
    ).fetchall()

    assert rows == [
        ("coinbase", 79_056.2, SOURCE_TIMESTAMP),
        ("okx", 79_111.8, SOURCE_TIMESTAMP),
    ]
