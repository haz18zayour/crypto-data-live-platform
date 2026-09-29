from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.okx_derivatives import (
    FundingRateOk,
    fetch_btc_funding_rate_history,
)
from ingest.persist import persist_datapoint
from ingest.pipeline import FullAssetRun
from ingest.registry import load_registry
from ingest.status import Ok

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, raw_value = line.partition("=")
            if separator and key.strip() == name and raw_value.strip():
                return raw_value.strip().strip("'\"")

    return None


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or _env_value("DATABASE_URL")
    if database_url:
        return database_url
    raise RuntimeError(
        "Backfill seam tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_backfill_seam_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError as error:
        pytest.skip(
            "PostgreSQL backfill seam tests could not connect; check "
            f"TEST_DATABASE_URL, DATABASE_URL, or DATABASE_URL in .env.local: {error}"
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
            connection.execute(sql.SQL("create schema {}").format(sql.Identifier(schema)))
            connection.execute(
                sql.SQL("grant usage on schema {} to anon, authenticated").format(
                    sql.Identifier(schema)
                )
            )
            schema_name = sql.Identifier(schema).as_string(connection)
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{schema_name}."
                )
                connection.execute(migration_sql)
        connection.execute(sql.SQL("set search_path to {}").format(sql.Identifier(schema)))

        try:
            yield connection
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(schema))
            )


def _definition(key: str):
    return next(entry for entry in load_registry().root if entry.key == key)


def test_backfill_run_cannot_splice_a_historical_value_into_current_board_views(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    definition = _definition("btc_daily_close")
    live_timestamp = datetime.now(UTC) - timedelta(hours=1)
    backfill_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    live_id = persist_datapoint(
        postgres,
        definition=definition,
        asset="BTC",
        measured_on="BTC",
        result=Ok(value=79_111.8, source_timestamp=live_timestamp),
    )

    def adversarial_backfill(_definition) -> FullAssetRun:
        return FullAssetRun(
            indicators={
                "btc_daily_close": Ok(
                    value=42_024.0,
                    source_timestamp=backfill_timestamp,
                )
            },
            history={},
        )

    row_ids = run_backfill(
        postgres,
        indicator_key="btc_daily_close",
        recipes={**BACKFILL_RECIPES, "okx_candles": adversarial_backfill},
    )

    assert row_ids
    backfill_id = row_ids[0]
    assert backfill_id > live_id
    board_rows = postgres.execute(
        """
        select id, value, origin, source_timestamp
        from board_read
        where indicator_key = 'btc_daily_close' and asset = 'BTC'
        """
    ).fetchall()
    read_rows = postgres.execute(
        """
        select id, value, origin, source_timestamp
        from datapoints_read
        where indicator_key = 'btc_daily_close' and asset = 'BTC'
        order by id
        """
    ).fetchall()

    assert board_rows == [(live_id, 79_111.8, "live", live_timestamp)]
    assert read_rows == [(live_id, 79_111.8, "live", live_timestamp)]
    assert postgres.execute(
        "select origin from datapoints where id = %s",
        (backfill_id,),
    ).fetchone() == ("backfill",)


@pytest.mark.integration
def test_live_backfilled_funding_overlap_matches_fresh_live_endpoint_value(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    row_ids = run_backfill(postgres, indicator_key="btc_funding_rate")
    live = fetch_btc_funding_rate_history()

    assert isinstance(live, FundingRateOk)
    persisted = postgres.execute(
        """
        select value, source_timestamp, endpoint, source_field, origin
        from datapoints
        where id = any(%s)
          and indicator_key = 'btc_funding_rate'
          and source_timestamp = %s
        """,
        (list(row_ids), live.source_timestamp),
    ).fetchone()

    assert persisted is not None, (
        "The seam check must land inside the overlap: the backfill page did not "
        f"persist the live endpoint's newest settled timestamp {live.source_timestamp}."
    )
    value, source_timestamp, endpoint, source_field, origin = persisted
    assert origin == "backfill"
    assert "before=1" in endpoint
    assert "vendor-bounded backfill page" in source_field
    assert source_timestamp == live.source_timestamp
    assert float(value) == pytest.approx(live.value, rel=1e-12, abs=0.0)
