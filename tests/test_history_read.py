from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
FETCHED_AT = datetime(2026, 9, 28, tzinfo=UTC)

pytestmark = pytest.mark.integration


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or _env_value("DATABASE_URL")
    if database_url:
        return database_url

    raise RuntimeError(
        "PostgreSQL history_read tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip().strip("'\"")

    return None


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[psycopg.Connection[tuple[object, ...]], str]]:
    schema = f"test_history_read_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL history_read tests could not connect; check TEST_DATABASE_URL, "
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
    asset: str = "BTC",
    value: float | None = 1.0,
    status: str = "OK",
    reason: str | None = None,
    source_vendor: str = "okx",
    source_timestamp: datetime | None = None,
    fetched_at: datetime = FETCHED_AT,
    origin: str = "live",
) -> int:
    row = connection.execute(
        """
        insert into datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp,
          origin
        ) values (
          %s, %s, %s, %s, %s, %s,
          %s, 'https://example.test/history', 'value', %s, %s, %s
        )
        returning id
        """,
        (
            indicator_key,
            asset,
            asset,
            value,
            status,
            reason,
            source_vendor,
            fetched_at,
            source_timestamp,
            origin,
        ),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _history_read(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    indicator_key: str,
    asset: str = "BTC",
    source_vendor: str = "okx",
    point_limit: int = 10,
) -> list[dict[str, object]]:
    row = connection.execute(
        "select history_read(%s, %s, %s, %s)",
        (indicator_key, asset, source_vendor, point_limit),
    ).fetchone()
    assert row is not None
    points = row[0]
    assert isinstance(points, list)
    return points


def test_history_read_returns_at_most_the_requested_recent_live_or_backfill_points_newest_first(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"bounded_{uuid4().hex}"
    for days_ago, origin in ((4, "live"), (3, "backfill"), (2, "live"), (1, "backfill")):
        _insert(
            connection,
            indicator_key=key,
            value=100.0 + days_ago,
            source_timestamp=FETCHED_AT - timedelta(days=days_ago),
            origin=origin,
        )

    points = _history_read(connection, indicator_key=key, point_limit=3)

    assert [point["value"] for point in points] == [101.0, 102.0, 103.0]
    assert [point["origin"] for point in points] == ["backfill", "live", "backfill"]
    assert len(points) == 3


def test_history_read_orders_by_source_timestamp_and_excludes_null_timestamp_absences(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"ordered_{uuid4().hex}"
    older_id = _insert(
        connection,
        indicator_key=key,
        value=1.0,
        source_timestamp=FETCHED_AT - timedelta(days=2),
    )
    newer_id = _insert(
        connection,
        indicator_key=key,
        value=2.0,
        source_timestamp=FETCHED_AT - timedelta(days=1),
    )
    _insert(
        connection,
        indicator_key=key,
        value=None,
        status="UNAVAILABLE",
        reason="FETCH_FAILED",
        source_timestamp=None,
    )

    okx_points = _history_read(connection, indicator_key=key, source_vendor="okx")

    assert [point["id"] for point in okx_points] == [newer_id, older_id]


def test_history_read_defines_id_desc_as_the_equal_timestamp_tie_break(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres

    definition = connection.execute(
        """
        select pg_get_functiondef(p.oid)
        from pg_proc p
          join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = %s
          and p.proname = 'history_read'
        """,
        (schema,),
    ).fetchone()

    assert definition is not None
    assert "order by source_timestamp desc, id desc" in str(definition[0]).lower()


def test_history_read_pins_to_one_source_vendor_per_call(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    key = f"vendor_{uuid4().hex}"
    _insert(
        connection,
        indicator_key=key,
        value=78_900.0,
        source_vendor="okx",
        source_timestamp=FETCHED_AT - timedelta(minutes=2),
    )
    _insert(
        connection,
        indicator_key=key,
        value=78_910.0,
        source_vendor="coinbase",
        source_timestamp=FETCHED_AT - timedelta(minutes=1),
    )

    points = _history_read(connection, indicator_key=key, source_vendor="okx")

    assert [point["source_vendor"] for point in points] == ["okx"]
    assert [point["value"] for point in points] == [78_900.0]


def test_history_read_returns_empty_array_for_a_cell_with_no_rows(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres

    points = _history_read(
        connection,
        indicator_key=f"missing_{uuid4().hex}",
        asset="SOL",
        source_vendor="okx",
    )

    assert points == []


def test_anon_can_execute_history_read_and_receives_one_json_array_under_the_row_cap(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    key = f"anon_history_{uuid4().hex}"
    for offset in range(60):
        _insert(
            connection,
            indicator_key=key,
            value=float(offset),
            source_timestamp=FETCHED_AT - timedelta(minutes=offset),
        )

    function_name = f"{schema}.history_read(text,text,text,integer)"
    execute_granted = connection.execute(
        "select has_function_privilege('anon', %s::text, 'EXECUTE')",
        (function_name,),
    ).fetchone()
    with connection.transaction(force_rollback=True):
        connection.execute("set local role anon")
        row = connection.execute(
            "select history_read(%s, 'BTC', 'okx', 60)",
            (key,),
        ).fetchone()

    assert execute_granted == (True,)
    assert row is not None
    assert isinstance(row[0], list)
    assert len(row[0]) == 60


def test_live_postgrest_history_read_for_a_real_cell_returns_one_bounded_array_under_the_default_row_cap() -> None:
    supabase_url = _env_value("VITE_SUPABASE_URL") or _env_value("SUPABASE_URL")
    anon_key = _env_value("VITE_SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        raise RuntimeError(
            "Live PostgREST history_read test requires VITE_SUPABASE_URL or "
            "SUPABASE_URL, plus VITE_SUPABASE_ANON_KEY"
        )

    response = httpx.post(
        f"{supabase_url.rstrip('/')}/rest/v1/rpc/history_read",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        },
        json={
            "p_indicator_key": "btc_daily_close",
            "p_asset": "BTC",
            "p_source_vendor": "okx",
            "p_point_limit": 500,
        },
        timeout=20,
    )

    assert response.status_code == 200, response.text
    points = response.json()
    assert isinstance(points, list)
    assert 0 < len(points) <= 500
    assert all(point["indicator_key"] == "btc_daily_close" for point in points)
    assert all(point["asset"] == "BTC" for point in points)
    assert all(point["source_vendor"] == "okx" for point in points)
