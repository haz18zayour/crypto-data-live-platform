from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from ingest.registry import load_registry

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
INTEGRITY_READ_SQL = (
    MIGRATIONS / "20260929120000_create_integrity_read_rpc.sql"
).read_text(encoding="utf-8")
NOW = datetime.now(UTC).replace(microsecond=0)


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or _env_value("DATABASE_URL")
    if database_url:
        return database_url

    raise RuntimeError(
        "PostgreSQL integrity_read tests require TEST_DATABASE_URL, DATABASE_URL, "
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


@pytest.fixture()
def postgres() -> Iterator[tuple[psycopg.Connection[tuple[object, ...]], str]]:
    schema = f"test_integrity_read_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError as error:
        pytest.skip(
            "PostgreSQL integrity_read tests could not connect; check "
            "TEST_DATABASE_URL, DATABASE_URL, or DATABASE_URL in .env.local"
            f": {error}"
        )

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


def _registry_payload() -> list[dict[str, Any]]:
    return [entry.model_dump(mode="json") for entry in load_registry().root]


def _registry_json() -> Jsonb:
    return Jsonb(_registry_payload())


def _entry(key: str) -> object:
    return next(entry for entry in load_registry().root if entry.key == key)


def _insert(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    indicator_key: str,
    asset: str,
    source_vendor: str,
    value: float,
    source_timestamp: datetime,
    fetched_at: datetime | None = None,
) -> None:
    if fetched_at is None:
        fetched_at = source_timestamp + timedelta(minutes=5)
    connection.execute(
        """
        insert into datapoints (
          indicator_key, asset, measured_on, value, status, reason,
          source_vendor, endpoint, source_field, fetched_at, source_timestamp, origin
        ) values (
          %s, %s, %s, %s, 'OK', null,
          %s, 'https://example.test/integrity', 'value', %s, %s, 'live'
        )
        on conflict (indicator_key, asset, source_vendor, source_timestamp)
        do update set value = excluded.value, fetched_at = excluded.fetched_at
        """,
        (
            indicator_key,
            asset,
            asset,
            value,
            source_vendor,
            fetched_at,
            source_timestamp,
        ),
    )


def _integrity_read(
    connection: psycopg.Connection[tuple[object, ...]],
) -> dict[tuple[str, str, str], dict[str, object]]:
    row = connection.execute(
        "select integrity_read(%s)",
        (_registry_json(),),
    ).fetchone()
    assert row is not None
    rows = row[0]
    assert isinstance(rows, list)
    return {
        (str(item["indicator_key"]), str(item["asset"]), str(item["source_vendor"])): item
        for item in rows
    }


def test_integrity_read_migration_is_additive_rpc_only() -> None:
    sql_text = INTEGRITY_READ_SQL.lower()

    assert "create or replace function public.integrity_read(p_registry jsonb)" in sql_text
    assert "returns jsonb" in sql_text
    assert "statement_timestamp() as computed_at" in sql_text
    assert "from public.datapoints" in sql_text
    assert "jsonb_to_recordset" in sql_text
    assert "select distinct on (" in sql_text
    assert "d.source_timestamp" in sql_text
    assert "grant execute on function public.integrity_read(jsonb) to anon, authenticated" in sql_text
    assert "notify pgrst, 'reload schema'" in sql_text
    assert "alter table public.datapoints" not in sql_text
    assert "create type public.datapoint_status" not in sql_text
    assert "alter type public.datapoint_status" not in sql_text


def test_integrity_read_computes_freshness_and_frozen_states_from_real_registry_rows(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres
    btc_close = _entry("btc_daily_close")
    btc_mvrv = _entry("btc_mvrv")
    btc_open_interest = _entry("btc_open_interest")

    for offset_days in (0, 1, 2):
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="BTC",
            source_vendor="okx",
            value=78000.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )
    for offset_days, value in ((0, 55.0), (1, 54.0), (2, 53.0)):
        _insert(
            connection,
            indicator_key="btc_rsi",
            asset="BTC",
            source_vendor="okx",
            value=value,
            source_timestamp=NOW - timedelta(days=offset_days),
        )

    _insert(
        connection,
        indicator_key="btc_mvrv",
        asset="BTC",
        source_vendor="coinmetrics",
        value=2.1,
        source_timestamp=NOW
        - timedelta(seconds=int(btc_mvrv.freshness_warn_seconds) + 60),
    )
    _insert(
        connection,
        indicator_key="btc_open_interest",
        asset="BTC",
        source_vendor="okx",
        value=8_000_000_000.0,
        source_timestamp=NOW
        - timedelta(seconds=int(btc_open_interest.freshness_stale_seconds) + 60),
    )

    for offset_hours in (0, 8, 16, 24):
        _insert(
            connection,
            indicator_key="btc_funding_rate",
            asset="BTC",
            source_vendor="okx",
            value=0.0001,
            source_timestamp=NOW - timedelta(hours=offset_hours),
        )

    _insert(
        connection,
        indicator_key="stablecoin_supply",
        asset="ETH",
        source_vendor="defillama",
        value=124_000_000_000.0,
        source_timestamp=NOW,
    )

    for offset_days in (0, 1, 2):
        _insert(
            connection,
            indicator_key="eth_rsi",
            asset="ETH",
            source_vendor="okx",
            value=42.0,
            source_timestamp=NOW - timedelta(days=offset_days),
        )

    rows = _integrity_read(connection)

    root = rows[("btc_daily_close", "BTC", "okx")]
    assert root["freshness_state"] == "fresh"
    assert root["frozen"] is True
    assert root["frozen_state"] == "frozen"
    assert root["frozen_after_observations"] == btc_close.frozen_after_observations
    assert root["computed_at"] is not None

    dependent = rows[("btc_rsi", "BTC", "okx")]
    assert dependent["derives_from"] == "btc_daily_close"
    assert dependent["frozen"] is True
    assert dependent["frozen_state"] == "frozen"

    expected_constant = rows[("btc_funding_rate", "BTC", "okx")]
    assert expected_constant["frozen"] is False
    assert expected_constant["frozen_state"] == "expected_constant"

    unmeasurable = rows[("stablecoin_supply", "ETH", "defillama")]
    assert unmeasurable["freshness_state"] == "unmeasurable"
    assert unmeasurable["freshness_unmeasurable_reason"]

    propagation_unavailable = rows[("eth_rsi", "ETH", "okx")]
    assert propagation_unavailable["frozen"] is None
    assert propagation_unavailable["frozen_state"] == "propagation_unavailable"
    assert propagation_unavailable["frozen_propagation_unavailable_reason"]

    assert rows[("btc_mvrv", "BTC", "coinmetrics")]["freshness_state"] == "warn"
    assert rows[("btc_open_interest", "BTC", "okx")]["freshness_state"] == "stale"


def test_integrity_read_counts_distinct_observations_and_clears_on_a_changed_latest_value(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, _ = postgres

    for offset_days in (0, 1):
        timestamp = NOW - timedelta(days=offset_days)
        _insert(
            connection,
            indicator_key="btc_daily_close",
            asset="BTC",
            source_vendor="okx",
            value=78000.0,
            source_timestamp=timestamp,
            fetched_at=timestamp + timedelta(minutes=5),
        )
    _insert(
        connection,
        indicator_key="btc_daily_close",
        asset="BTC",
        source_vendor="okx",
        value=78000.0,
        source_timestamp=NOW,
        fetched_at=NOW + timedelta(hours=1),
    )

    row = _integrity_read(connection)[("btc_daily_close", "BTC", "okx")]
    assert row["frozen"] is False
    assert row["frozen_state"] == "not_frozen"

    _insert(
        connection,
        indicator_key="btc_daily_close",
        asset="BTC",
        source_vendor="okx",
        value=78000.0,
        source_timestamp=NOW - timedelta(days=2),
    )
    row = _integrity_read(connection)[("btc_daily_close", "BTC", "okx")]
    assert row["frozen"] is True

    _insert(
        connection,
        indicator_key="btc_daily_close",
        asset="BTC",
        source_vendor="okx",
        value=78001.0,
        source_timestamp=NOW + timedelta(days=1),
    )
    row = _integrity_read(connection)[("btc_daily_close", "BTC", "okx")]
    assert row["frozen"] is False


def test_anon_can_execute_integrity_read(
    postgres: tuple[psycopg.Connection[tuple[object, ...]], str],
) -> None:
    connection, schema = postgres
    _insert(
        connection,
        indicator_key="btc_daily_close",
        asset="BTC",
        source_vendor="okx",
        value=78000.0,
        source_timestamp=NOW,
    )

    function_name = f"{schema}.integrity_read(jsonb)"
    execute_granted = connection.execute(
        "select has_function_privilege('anon', %s::text, 'EXECUTE')",
        (function_name,),
    ).fetchone()
    with connection.transaction(force_rollback=True):
        connection.execute("set local role anon")
        row = connection.execute("select integrity_read(%s)", (_registry_json(),)).fetchone()

    assert execute_granted == (True,)
    assert row is not None
    assert isinstance(row[0], list)
    assert row[0][0]["indicator_key"] == "btc_daily_close"


@pytest.mark.integration
def test_live_postgrest_integrity_read_for_a_real_cell_returns_integrity_state() -> None:
    supabase_url = _env_value("VITE_SUPABASE_URL") or _env_value("SUPABASE_URL")
    anon_key = _env_value("VITE_SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        raise RuntimeError(
            "Live PostgREST integrity_read test requires VITE_SUPABASE_URL or "
            "SUPABASE_URL, plus VITE_SUPABASE_ANON_KEY"
        )

    response = httpx.post(
        f"{supabase_url.rstrip('/')}/rest/v1/rpc/integrity_read",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        },
        json={"p_registry": _registry_payload()},
        timeout=20,
    )

    assert response.status_code == 200, response.text
    rows = response.json()
    assert isinstance(rows, list)
    btc_rows = [
        row
        for row in rows
        if row["indicator_key"] == "btc_daily_close"
        and row["asset"] == "BTC"
        and row["source_vendor"] == "okx"
    ]
    assert btc_rows
    assert btc_rows[0]["computed_at"]
    assert btc_rows[0]["freshness_state"] in {
        "fresh",
        "warn",
        "stale",
        "unmeasurable",
    }
    assert btc_rows[0]["frozen_state"] in {
        "frozen",
        "not_frozen",
        "expected_constant",
        "propagation_unavailable",
        "root_unavailable",
    }
