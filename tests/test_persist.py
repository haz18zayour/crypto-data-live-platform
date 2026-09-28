from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from ingest.persist import persist_datapoint
from ingest.pipeline import run_pipeline
from ingest.registry import IndicatorDefinition, load_registry
from ingest.status import Ok, Reason, Unavailable

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
FETCHED_AT = datetime(2026, 9, 9, 12, tzinfo=UTC)
SOURCE_TIMESTAMP = datetime(2026, 9, 8, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 9, 11, 12, tzinfo=UTC)


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
        "PostgreSQL persistence tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_persist_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL persistence tests could not connect; check TEST_DATABASE_URL, "
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
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{sql.Identifier(schema).as_string(connection)}."
                )
                connection.execute(migration_sql)
        connection.execute(
            sql.SQL("set search_path to {}").format(sql.Identifier(schema))
        )

        try:
            yield connection
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(
                    sql.Identifier(schema)
                )
            )


@pytest.fixture
def definition() -> IndicatorDefinition:
    return IndicatorDefinition(
        key=f"test_indicator_{uuid4().hex}",
        vendor="registry-vendor",
        endpoint="https://registry.example.test/market-data",
        source_field="payload.close",
        definable_for=("BTC",),
        expected_update_interval_seconds=86_400,
        freshness_warn_seconds=108_000,
        freshness_stale_seconds=172_800,
    )


class NoDatabaseConnection:
    def transaction(self) -> Never:
        raise AssertionError("database was reached before validation")


class FakeCursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class FakeTransaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class RecordingConnection:
    def __init__(self, existing_row: tuple[object, ...] | None = None) -> None:
        self.existing_row = existing_row
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    def execute(
        self, statement: str, params: tuple[object, ...] = ()
    ) -> FakeCursor:
        self.statements.append((statement, params))
        if "from datapoints" in statement:
            return FakeCursor(self.existing_row)
        if "returning id" in statement:
            return FakeCursor((self.existing_row[0] if self.existing_row else 123,))
        return FakeCursor(None)


def _persisted_write(
    connection: RecordingConnection,
) -> tuple[str, tuple[object, ...]]:
    for statement, params in reversed(connection.statements):
        if "returning id" in statement:
            return statement, params
    raise AssertionError("no persisted write was issued")


def test_migration_adds_nullable_reference_period_and_published_at_columns() -> None:
    migration = (
        MIGRATIONS / "20260927120000_add_datapoint_reference_period_and_published_at.sql"
    ).read_text(encoding="utf-8")

    assert "alter table public.datapoints" in migration
    assert "add column reference_period text" in migration
    assert "add column published_at timestamptz" in migration
    assert "not null" not in migration.lower().split(";", maxsplit=1)[0]


def test_migration_adds_not_null_origin_defaulting_to_live_and_filters_read_views() -> None:
    migration = (
        MIGRATIONS / "20260928120000_add_datapoint_origin_and_filter_live_reads.sql"
    ).read_text(encoding="utf-8")

    assert "alter table public.datapoints" in migration
    assert "add column origin text not null default 'live'" in migration
    assert "create or replace view public.datapoints_read" in migration
    assert "create or replace view public.board_read" in migration
    assert migration.count("where origin = 'live'") == 2


@pytest.mark.integration
def test_adversarial_backfill_row_fetched_now_is_excluded_from_live_read_views(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    key = f"origin_guard_{uuid4().hex}"
    live_timestamp = datetime(2026, 9, 8, tzinfo=UTC)
    backfill_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    live_row = postgres.execute(
        """
        insert into datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp,
          origin
        ) values (
          %s, 'BTC', 'BTC', 79111.8, 'OK', null,
          'okx', 'https://www.okx.com/api/v5/market/candles',
          'candle[4] where candle[8] = 1', %s, %s, 'live'
        )
        returning id
        """,
        (key, FETCHED_AT, live_timestamp),
    ).fetchone()
    backfill_row = postgres.execute(
        """
        insert into datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp,
          origin
        ) values (
          %s, 'BTC', 'BTC', 42024.0, 'OK', null,
          'okx', 'https://www.okx.com/api/v5/market/candles',
          'candle[4] where candle[8] = 1',
          %s, %s, 'backfill'
        )
        returning id
        """,
        (key, FETCHED_AT + timedelta(minutes=1), backfill_timestamp),
    ).fetchone()
    assert live_row is not None
    assert backfill_row is not None
    live_id = int(live_row[0])
    backfill_id = int(backfill_row[0])

    board_rows = postgres.execute(
        """
        select id, value, origin, fetched_at, source_timestamp
        from board_read
        where indicator_key = %s
        """,
        (key,),
    ).fetchall()
    read_rows = postgres.execute(
        """
        select id, value, origin, fetched_at, source_timestamp
        from datapoints_read
        where indicator_key = %s
        order by id
        """,
        (key,),
    ).fetchall()
    raw_rows = postgres.execute(
        """
        select id, origin, fetched_at, source_timestamp
        from datapoints
        where indicator_key = %s
        order by id
        """,
        (key,),
    ).fetchall()

    assert backfill_id > live_id
    assert raw_rows == [
        (live_id, "live", FETCHED_AT, live_timestamp),
        (
            backfill_id,
            "backfill",
            FETCHED_AT + timedelta(minutes=1),
            backfill_timestamp,
        ),
    ]
    assert board_rows == [(live_id, 79111.8, "live", FETCHED_AT, live_timestamp)]
    assert read_rows == [(live_id, 79111.8, "live", FETCHED_AT, live_timestamp)]


def test_existing_call_pattern_writes_null_reference_period_and_published_at_offline(
    definition: IndicatorDefinition,
) -> None:
    connection = RecordingConnection()

    row_id = persist_datapoint(
        connection,  # type: ignore[arg-type]
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    statement, params = _persisted_write(connection)
    assert row_id == 123
    assert "reference_period, published_at" in statement
    assert params[-2:] == (None, None)
    assert params[-3] == "live"


def test_origin_is_written_when_provided_offline(
    definition: IndicatorDefinition,
) -> None:
    connection = RecordingConnection()

    persist_datapoint(
        connection,  # type: ignore[arg-type]
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        origin="backfill",
    )

    statement, params = _persisted_write(connection)
    assert "origin, reference_period, published_at" in statement
    assert params[-3:] == ("backfill", None, None)


def test_reference_period_and_published_at_are_written_when_provided_offline(
    definition: IndicatorDefinition,
) -> None:
    connection = RecordingConnection()

    persist_datapoint(
        connection,  # type: ignore[arg-type]
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        reference_period="2026-08",
        published_at=PUBLISHED_AT,
    )

    statement, params = _persisted_write(connection)
    assert "reference_period, published_at" in statement
    assert params[-2:] == ("2026-08", PUBLISHED_AT)


@pytest.mark.parametrize(
    ("reference_period", "published_at"),
    (
        ("2026-08", None),
        (None, PUBLISHED_AT),
    ),
)
def test_reference_period_and_published_at_are_independently_nullable_offline(
    definition: IndicatorDefinition,
    reference_period: str | None,
    published_at: datetime | None,
) -> None:
    connection = RecordingConnection()

    persist_datapoint(
        connection,  # type: ignore[arg-type]
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        reference_period=reference_period,
        published_at=published_at,
    )

    _, params = _persisted_write(connection)
    assert params[-2:] == (reference_period, published_at)


@pytest.mark.integration
def test_unavailable_result_is_persisted_with_reason_and_null_value(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Unavailable(reason=Reason.FETCH_FAILED),
    )

    row = postgres.execute(
        "select status, reason, value from datapoints where id = %s", (row_id,)
    ).fetchone()

    assert row == ("UNAVAILABLE", "FETCH_FAILED", None)


@pytest.mark.integration
def test_provenance_fields_are_copied_from_registry_entry(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    row = postgres.execute(
        """
        select source_vendor, endpoint, source_field
        from datapoints
        where id = %s
        """,
        (row_id,),
    ).fetchone()

    assert row == (definition.vendor, definition.endpoint, definition.source_field)


def test_mismatched_measured_on_raises_before_reaching_database(
    definition: IndicatorDefinition,
) -> None:
    with pytest.raises(ValueError, match="measured_on must equal asset"):
        persist_datapoint(
            NoDatabaseConnection(),  # type: ignore[arg-type]
            definition=definition,
            asset="SOL",
            measured_on="BTC",
            result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        )


@pytest.mark.integration
def test_writer_sets_fetched_at_and_uses_fetcher_source_timestamp(
    monkeypatch: pytest.MonkeyPatch,
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    monkeypatch.setattr("ingest.persist._utc_now", lambda: FETCHED_AT)
    result = Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP)

    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=result,
    )
    row = postgres.execute(
        "select fetched_at, source_timestamp from datapoints where id = %s", (row_id,)
    ).fetchone()

    assert row == (FETCHED_AT, result.source_timestamp)
    assert row[0] != row[1]


@pytest.mark.integration
def test_existing_call_pattern_defaults_origin_to_live(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    row = postgres.execute(
        "select origin from datapoints where id = %s", (row_id,)
    ).fetchone()

    assert row == ("live",)


@pytest.mark.integration
def test_origin_is_written_when_provided(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        origin="backfill",
    )

    row = postgres.execute(
        "select origin from datapoints where id = %s", (row_id,)
    ).fetchone()

    assert row == ("backfill",)


@pytest.mark.integration
def test_existing_call_pattern_writes_null_reference_period_and_published_at(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    row = postgres.execute(
        "select reference_period, published_at from datapoints where id = %s",
        (row_id,),
    ).fetchone()

    assert row == (None, None)


@pytest.mark.integration
def test_reference_period_and_published_at_are_written_when_provided(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        reference_period="2026-08",
        published_at=PUBLISHED_AT,
    )

    row = postgres.execute(
        "select reference_period, published_at from datapoints where id = %s",
        (row_id,),
    ).fetchone()

    assert row == ("2026-08", PUBLISHED_AT)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("reference_period", "published_at"),
    (
        ("2026-08", None),
        (None, PUBLISHED_AT),
    ),
)
def test_reference_period_and_published_at_are_independently_nullable(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
    reference_period: str | None,
    published_at: datetime | None,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
        reference_period=reference_period,
        published_at=published_at,
    )

    row = postgres.execute(
        "select reference_period, published_at from datapoints where id = %s",
        (row_id,),
    ).fetchone()

    assert row == (reference_period, published_at)


def test_future_source_timestamp_is_rejected_before_reaching_database(
    monkeypatch: pytest.MonkeyPatch,
    definition: IndicatorDefinition,
) -> None:
    monkeypatch.setattr("ingest.persist._utc_now", lambda: FETCHED_AT)

    with pytest.raises(ValueError, match="source_timestamp cannot be in the future"):
        persist_datapoint(
            NoDatabaseConnection(),  # type: ignore[arg-type]
            definition=definition,
            asset="BTC",
            measured_on="BTC",
            result=Ok(
                value=42.5,
                source_timestamp=FETCHED_AT + timedelta(microseconds=1),
            ),
        )


@pytest.mark.integration
def test_source_field_is_persisted_and_non_empty(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    row_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    source_field = postgres.execute(
        "select source_field from datapoints where id = %s", (row_id,)
    ).fetchone()[0]

    assert source_field == definition.source_field
    assert source_field.strip()


@pytest.mark.integration
def test_same_source_timestamp_updates_instead_of_inserting_a_duplicate(
    postgres: psycopg.Connection[tuple[object, ...]],
    definition: IndicatorDefinition,
) -> None:
    first_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=41.0, source_timestamp=SOURCE_TIMESTAMP),
    )
    second_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=42.5, source_timestamp=SOURCE_TIMESTAMP),
    )

    rows = postgres.execute(
        """
        select id, value from datapoints
        where indicator_key = %s and asset = 'BTC' and source_timestamp = %s
        """,
        (definition.key, SOURCE_TIMESTAMP),
    ).fetchall()

    assert first_id == second_id
    assert rows == [(first_id, 42.5)]


@pytest.mark.integration
def test_pipeline_without_fetcher_records_not_fetched(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    row_id = run_pipeline(postgres, fetcher=None)

    row = postgres.execute(
        "select status, reason, value from datapoints where id = %s", (row_id,)
    ).fetchone()

    assert row == ("UNAVAILABLE", "NOT_FETCHED", None)


@pytest.mark.integration
def test_full_pipeline_fetches_live_okx_and_writes_complete_provenance(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    before = datetime.now(UTC)
    row_id = run_pipeline(postgres)
    after = datetime.now(UTC)

    row = postgres.execute(
        """
        select indicator_key, asset, measured_on, value, status, reason,
               source_vendor, endpoint, source_field, fetched_at, source_timestamp
        from datapoints
        where id = %s
        """,
        (row_id,),
    ).fetchone()
    definition = load_registry().root[0]

    assert row is not None
    assert row[:6] == (definition.key, "BTC", "BTC", row[3], "OK", None)
    assert isinstance(row[3], float)
    assert row[6:9] == (
        definition.vendor,
        definition.endpoint,
        definition.source_field,
    )
    assert before <= row[9] <= after
    assert row[10] < row[9]
    assert all(row[index] for index in (6, 7, 8, 9, 10))
