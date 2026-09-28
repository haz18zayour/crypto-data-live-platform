from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
FETCHED_AT = datetime(2026, 9, 13, tzinfo=UTC)

pytestmark = pytest.mark.integration


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
        "PostgreSQL board_read tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[psycopg.Connection[tuple[object, ...]], str]]:
    schema = f"test_board_read_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL board_read tests could not connect; check TEST_DATABASE_URL, "
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
            # Supabase grants anon usage on `public`; the throwaway schema needs the same.
            connection.execute(
                sql.SQL("grant usage on schema {} to anon, authenticated").format(
                    sql.Identifier(schema)
                )
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


def _insert(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    indicator_key: str,
    asset: str,
    value: float,
    fetched_at: datetime,
    source_timestamp: datetime | None = None,
    source_vendor: str = "okx",
    origin: str = "live",
) -> int:
    if source_timestamp is None:
        source_timestamp = fetched_at - timedelta(hours=1)
    row = connection.execute(
        """
        insert into datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp,
          origin
        ) values (
          %s, %s, %s, %s, 'OK', null,
          %s, 'https://www.okx.com/api/v5/market/candles',
          'candle[4] where candle[8] = 1', %s, %s, %s
        )
        returning id
        """,
        (
            indicator_key,
            asset,
            asset,
            value,
            source_vendor,
            fetched_at,
            source_timestamp,
            origin,
        ),
    ).fetchone()
    assert row is not None
    return int(row[0])


def test_board_read_returns_exactly_one_row_for_every_distinct_indicator_key_and_asset_pair_in_datapoints(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    prefix = f"distinct_{uuid4().hex}"
    for asset in ("BTC", "ETH", "SOL"):
        for family in ("close", "rsi_14"):
            for day in range(3):
                _insert(
                    connection,
                    indicator_key=f"{prefix}_{asset.lower()}_{family}",
                    asset=asset,
                    value=float(day),
                    fetched_at=FETCHED_AT - timedelta(days=day),
                )
    # Two venues for one cell is still one cell.
    _insert(
        connection,
        indicator_key=f"{prefix}_btc_close",
        asset="BTC",
        value=79_056.2,
        fetched_at=FETCHED_AT + timedelta(minutes=1),
        source_vendor="coinbase",
    )

    distinct_pairs = connection.execute(
        """
        select count(*) from (
          select distinct indicator_key, asset from datapoints
        ) pairs
        """
    ).fetchone()
    total_rows = connection.execute("select count(*) from datapoints").fetchone()
    board_rows = connection.execute("select count(*) from board_read").fetchone()
    duplicated_cells = connection.execute(
        """
        select indicator_key, asset
        from board_read
        group by indicator_key, asset
        having count(*) > 1
        """
    ).fetchall()
    missing_cells = connection.execute(
        """
        select distinct indicator_key, asset from datapoints
        except
        select indicator_key, asset from board_read
        """
    ).fetchall()

    assert distinct_pairs is not None and total_rows is not None
    assert board_rows is not None
    assert total_rows[0] > distinct_pairs[0]
    assert board_rows[0] == distinct_pairs[0]
    assert duplicated_cells == []
    assert missing_cells == []


def test_given_two_rows_for_one_cell_the_view_returns_the_one_with_the_later_fetched_at(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"latest_{uuid4().hex}"

    newer_id = _insert(
        connection,
        indicator_key=key,
        asset="BTC",
        value=79_111.8,
        fetched_at=FETCHED_AT,
    )
    # Inserted last, with the higher id, so neither insertion order nor id can pick it.
    older_id = _insert(
        connection,
        indicator_key=key,
        asset="BTC",
        value=78_834.1,
        fetched_at=FETCHED_AT - timedelta(days=1),
    )

    rows = connection.execute(
        "select id, value, fetched_at from board_read where indicator_key = %s",
        (key,),
    ).fetchall()

    assert older_id > newer_id
    assert rows == [(newer_id, 79_111.8, FETCHED_AT)]


def test_board_read_and_datapoints_read_ignore_backfill_even_when_it_was_fetched_later(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"origin_guard_{uuid4().hex}"
    live_id = _insert(
        connection,
        indicator_key=key,
        asset="BTC",
        value=79_111.8,
        fetched_at=FETCHED_AT,
        source_timestamp=datetime(2026, 9, 12, tzinfo=UTC),
        origin="live",
    )
    backfill_id = _insert(
        connection,
        indicator_key=key,
        asset="BTC",
        value=42_024.0,
        fetched_at=FETCHED_AT + timedelta(minutes=1),
        source_timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        origin="backfill",
    )
    other_origin_id = _insert(
        connection,
        indicator_key=key,
        asset="BTC",
        value=42_025.0,
        fetched_at=FETCHED_AT + timedelta(minutes=2),
        source_timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        origin="shadow",
    )

    board_rows = connection.execute(
        "select id, value, origin from board_read where indicator_key = %s",
        (key,),
    ).fetchall()
    read_rows = connection.execute(
        """
        select id, value, origin
        from datapoints_read
        where indicator_key = %s
        order by id
        """,
        (key,),
    ).fetchall()

    assert backfill_id > live_id
    assert other_origin_id > backfill_id
    assert board_rows == [(live_id, 79_111.8, "live")]
    assert read_rows == [(live_id, 79_111.8, "live")]


def test_board_read_exposes_every_column_the_page_needs_including_status_reason_source_vendor_and_source_timestamp(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    columns = [
        str(row[0])
        for row in connection.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = %s and table_name = 'board_read'
            order by ordinal_position
            """,
            (schema,),
        ).fetchall()
    ]

    assert "id" in columns
    assert "indicator_key" in columns
    assert "asset" in columns
    assert "measured_on" in columns
    assert "value" in columns
    assert "status" in columns
    assert "reason" in columns
    assert "source_vendor" in columns
    assert "endpoint" in columns
    assert "source_field" in columns
    assert "fetched_at" in columns
    assert "source_timestamp" in columns


def test_anon_can_select_from_board_read_and_cannot_insert_update_or_delete_through_it(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    key = f"anon_{uuid4().hex}"
    row_id = _insert(
        connection, indicator_key=key, asset="BTC", value=79_111.8, fetched_at=FETCHED_AT
    )

    reloptions = connection.execute(
        """
        select c.reloptions
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = %s and c.relname = 'board_read'
        """,
        (schema,),
    ).fetchone()
    assert reloptions is not None
    assert "security_invoker=true" in reloptions[0]

    view = f"{schema}.board_read"
    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        granted = connection.execute(
            "select has_table_privilege('anon', %s::text, %s::text)", (view, privilege)
        ).fetchone()
        assert granted == (privilege == "SELECT",), privilege

    with connection.transaction(force_rollback=True):
        connection.execute("set local role anon")
        visible = connection.execute(
            "select id, value from board_read where indicator_key = %s", (key,)
        ).fetchall()
    assert visible == [(row_id, 79_111.8)]

    writes = (
        (
            """
            insert into board_read (
              indicator_key, asset, measured_on, value, status,
              source_vendor, endpoint, source_field, fetched_at
            ) values (%s, 'BTC', 'BTC', 1.0, 'OK', 'okx', 'e', 'f', now())
            """,
            (key,),
        ),
        ("update board_read set value = 0.0 where indicator_key = %s", (key,)),
        ("delete from board_read where indicator_key = %s", (key,)),
    )
    for statement, params in writes:
        with (
            pytest.raises(psycopg.Error),
            connection.transaction(force_rollback=True),
        ):
            connection.execute("set local role anon")
            connection.execute(statement, params)

    unchanged = connection.execute(
        "select id, value from datapoints where indicator_key = %s", (key,)
    ).fetchall()
    assert unchanged == [(row_id, 79_111.8)]
