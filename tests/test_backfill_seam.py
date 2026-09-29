from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.defillama_stablecoins import (
    DEFILLAMA_STABLECOINCHAINS_ENDPOINT,
    DefiLlamaStablecoinSupplyOk,
    backfill_defillama_stablecoin_supply,
    fetch_stablecoin_supply,
)
from ingest.persist import persist_datapoint
from ingest.pipeline import FullAssetRun, persist_board
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


def _stablecoin_chart_row(timestamp: datetime, value: Decimal) -> dict[str, object]:
    return {
        "date": str(int(timestamp.timestamp())),
        "totalCirculatingUSD": {"peggedUSD": float(value)},
    }


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


def test_backfilled_overlap_matches_fresh_independent_live_endpoint_value(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    overlap_day = datetime(2026, 9, 28, tzinfo=UTC)
    live_read_time = overlap_day + timedelta(hours=12)
    seam_value = Decimal("146.25")
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == DEFILLAMA_STABLECOINCHAINS_ENDPOINT:
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Ethereum",
                        "totalCirculatingUSD": {"peggedUSD": float(seam_value)},
                    },
                    {
                        "name": "Solana",
                        "totalCirculatingUSD": {"peggedUSD": 16.0},
                    },
                    {
                        "name": "BSC",
                        "totalCirculatingUSD": {"peggedUSD": 13.0},
                    },
                ],
                request=request,
            )
        chain = request.url.path.rsplit("/", 1)[-1]
        values = {"Ethereum": seam_value, "Solana": Decimal("16.0"), "BSC": Decimal("13.0")}
        return httpx.Response(
            200,
            json=[_stablecoin_chart_row(overlap_day, values[chain])],
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        row_ids = run_backfill(
            postgres,
            indicator_key="stablecoin_supply",
            recipes={
                **BACKFILL_RECIPES,
                "defillama_stablecoincharts": lambda definition: (
                    backfill_defillama_stablecoin_supply(definition, client=client)
                ),
            },
        )
        live = fetch_stablecoin_supply("ETH", client=client, now=live_read_time)

    assert isinstance(live, DefiLlamaStablecoinSupplyOk)
    live_id = persist_board(
        postgres,
        FullAssetRun(indicators={"stablecoin_supply\x1fETH": live}, history={}),
    )[0]

    persisted_backfill = postgres.execute(
        """
        select value, source_timestamp, endpoint, source_field, origin, reference_period
        from datapoints
        where id = any(%s)
          and indicator_key = 'stablecoin_supply'
          and asset = 'ETH'
          and source_timestamp::date = %s
        """,
        (list(row_ids), overlap_day.date()),
    ).fetchone()
    persisted_live = postgres.execute(
        """
        select value, source_timestamp, endpoint, source_field, origin, reference_period
        from datapoints
        where id = %s
        """,
        (live_id,),
    ).fetchone()

    assert persisted_backfill is not None
    backfill_value, backfill_timestamp, backfill_endpoint, backfill_field, backfill_origin, reference_period = (
        persisted_backfill
    )
    assert persisted_live is not None
    live_value, live_timestamp, live_endpoint, live_field, live_origin, live_reference_period = (
        persisted_live
    )

    assert backfill_origin == "backfill"
    assert "stablecoincharts/Ethereum" in backfill_endpoint
    assert "/stablecoincharts/Ethereum" in backfill_field
    assert backfill_timestamp.date() == live_read_time.date()
    assert reference_period == live_read_time.date().isoformat()

    assert live_origin == "live"
    assert live_timestamp == live_read_time
    assert live_reference_period == "current"
    assert live_endpoint == DEFILLAMA_STABLECOINCHAINS_ENDPOINT
    assert "/stablecoinchains" in live_field

    assert Decimal(str(backfill_value)) == Decimal(str(live_value)) == live.value == seam_value
    assert any("/stablecoincharts/Ethereum" in url for url in requested_urls)
    assert requested_urls[-1] == DEFILLAMA_STABLECOINCHAINS_ENDPOINT


@pytest.mark.integration
def test_live_backfilled_and_live_defillama_endpoints_agree_at_the_real_seam(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    # The real cross-vendor-endpoint seam check research's blind-spot analysis calls
    # for: hit the REAL /stablecoincharts/{chain} (backfill) and /stablecoinchains
    # (live) endpoints independently - not a replay of one against itself - and confirm
    # they agree for the same chain on the same day. This test alone caught a real,
    # previously undiscovered defect: DefiLlamaStablecoinChartEntry's extra="forbid"
    # rejected every real /stablecoincharts response outright (it carries several
    # undeclared fields this project doesn't read), so the entire recipe was completely
    # non-functional against live data despite every offline (fixture-based) test
    # passing. Fixed in ingest/schemas.py before this test could pass.
    # The real endpoint returns full history (thousands of rows per chain since 2017)
    # with no server-side date filter. Persisting all of it would make this test take
    # tens of minutes for no added assurance - trimming to the last few days keeps the
    # real API call, real schema validation, and real persist path, while only writing
    # a handful of rows.
    cutoff = datetime.now(UTC) - timedelta(days=5)

    def recent_defillama_recipe(recipe_entry):
        runs = backfill_defillama_stablecoin_supply(recipe_entry)
        return tuple(
            run
            for run in runs
            if any(
                value.source_timestamp >= cutoff
                for value in run.indicators.values()
            )
        )

    row_ids = run_backfill(
        postgres,
        indicator_key="stablecoin_supply",
        recipes={
            **BACKFILL_RECIPES,
            "defillama_stablecoincharts": recent_defillama_recipe,
        },
    )
    assert row_ids

    today = datetime.now(UTC).date()
    backfilled = postgres.execute(
        """
        select value, endpoint, source_field
        from datapoints
        where id = any(%s)
          and asset = 'ETH'
          and source_timestamp::date = %s
        """,
        (list(row_ids), today),
    ).fetchone()
    assert backfilled is not None, "no backfilled ETH row for today's date"
    backfill_value, backfill_endpoint, backfill_field = backfilled
    assert "stablecoincharts/Ethereum" in backfill_endpoint
    assert "stablecoincharts/Ethereum" in backfill_field

    live = fetch_stablecoin_supply("ETH")
    assert isinstance(live, DefiLlamaStablecoinSupplyOk)

    # Both figures are read minutes apart from two genuinely different live endpoints,
    # and a real, continuously-updating on-chain total can move slightly between the
    # two calls - this is not a splice, it is two honest reads of a moving number. A
    # gross mismatch (wrong chain, wrong units, stale-by-days) would fail this bound;
    # ordinary intraday drift will not.
    relative_drift = abs(Decimal(str(backfill_value)) - live.value) / live.value
    assert relative_drift < Decimal("0.05"), (
        f"backfill={backfill_value} vs live={live.value} drift={relative_drift:.4%} - "
        "too large to be ordinary intraday movement; suspect a real splice"
    )
