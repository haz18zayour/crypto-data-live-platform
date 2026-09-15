from __future__ import annotations

import math
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest import heartbeat, pipeline
from ingest.fetchers.okx_derivatives import FundingRateOk, OpenInterestOk
from ingest.pipeline import (
    FetchedBars,
    FullAssetRun,
    FundingRateResult,
    OpenInterestResult,
    Venue,
    run_all_assets,
    run_pipeline,
)
from ingest.registry import IndicatorDefinition, load_registry
from ingest.status import Error, Ok, Reason, Result

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
SOURCE_TIMESTAMP = datetime(2026, 9, 10, tzinfo=UTC)


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if database_url:
        return database_url

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip("'\"")

    raise RuntimeError(
        "PostgreSQL board persistence tests require TEST_DATABASE_URL, "
        "DATABASE_URL, or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_persist_board_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "PostgreSQL board persistence tests could not connect; check "
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
            yield connection
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(
                    sql.Identifier(schema)
                )
            )


def _synthetic_bars(asset: str, required_bars: int) -> FetchedBars:
    offset = {"BTC": 40_000.0, "ETH": 2_000.0, "SOL": 100.0, "BNB": 500.0}[
        asset
    ]
    bars = tuple(
        {
            "high": offset + index * 0.2 + math.sin(index / 3) * 5 + 2,
            "low": offset + index * 0.2 + math.sin(index / 3) * 5 - 2,
            "close": offset + index * 0.2 + math.sin(index / 3) * 5,
            "volume": 1_000.0 + index,
        }
        for index in range(required_bars)
    )
    return FetchedBars(bars, SOURCE_TIMESTAMP)


def _fetch_bars(venue: Venue, asset: str, required_bars: int) -> FetchedBars:
    return _synthetic_bars(asset, required_bars)


def _fetch_funding_rate(asset: str) -> FundingRateResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return FundingRateOk(
        value=offset / 100_000,
        source_timestamp=SOURCE_TIMESTAMP,
        source_field=(
            "OKX funding-rate-history realizedRate; interval_seconds=28800 "
            "derived from the two newest consecutive fundingTime deltas"
        ),
    )


def _fetch_open_interest(asset: str) -> OpenInterestResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return OpenInterestOk(
        value=offset * 1_000_000,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def _full_board() -> pipeline.FullAssetRun:
    return run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
    )


def _board_definitions() -> tuple[IndicatorDefinition, ...]:
    return tuple(
        definition
        for definition in load_registry().root
        if definition.talib_function is not None
        or definition.response_model == "okx_funding_rate_history"
        or definition.response_model == "okx_open_interest"
    )


def test_full_run_writes_one_datapoint_row_per_computed_indicator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, Any]] = []

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    row_ids = run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    definitions = _board_definitions()
    assert len(definitions) == 52
    assert len(row_ids) == 52
    assert len(persisted) == 52
    assert {row["indicator_key"] for row in persisted} == {
        definition.key for definition in definitions
    }


def test_each_persisted_board_row_carries_schema_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        persisted.append(
            {
                "source_vendor": definition.vendor,
                "endpoint": definition.endpoint,
                "source_field": definition.source_field,
                "source_timestamp": (
                    result.source_timestamp
                    if isinstance(result, (Ok, FundingRateOk, OpenInterestOk))
                    else None
                ),
                "measured_on": measured_on,
                "asset": asset,
            }
        )
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(persisted) == 52
    assert all(row["source_vendor"] == "okx" for row in persisted)
    assert all(row["endpoint"] for row in persisted)
    assert all(row["source_field"] for row in persisted)
    assert all(row["source_timestamp"] == SOURCE_TIMESTAMP for row in persisted)
    assert all(row["measured_on"] == row["asset"] for row in persisted)


def test_non_ok_computed_result_is_persisted_with_status_and_reason_and_peers_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed_key = "btc_rsi"
    calculate = pipeline._calculate
    persisted: dict[str, Result] = {}

    def fail_one_indicator(
        definition: IndicatorDefinition, bars: tuple[dict[str, float], ...]
    ) -> float:
        if definition.key == failed_key:
            raise ValueError("forced computation failure")
        return calculate(definition, bars)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "_calculate", fail_one_indicator)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(persisted) == 52
    assert persisted[failed_key] == Error(
        reason=Reason.FETCH_FAILED,
        detail="btc_rsi computation failed: forced computation failure",
    )
    assert sum(isinstance(result, Ok) for result in persisted.values()) == 51


def test_full_run_persists_one_funding_rate_datapoint_per_asset_with_runtime_source_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, dict[str, object]] = {}

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        if definition.key.endswith("_funding_rate"):
            persisted[definition.key] = {
                "asset": asset,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_field": definition.source_field,
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {
        "btc_funding_rate",
        "eth_funding_rate",
        "sol_funding_rate",
        "bnb_funding_rate",
    }
    assert {row["asset"] for row in persisted.values()} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(row["status"] == "OK" for row in persisted.values())
    assert all(
        "interval_seconds=28800" in str(row["source_field"])
        for row in persisted.values()
    )


def test_full_run_persists_one_open_interest_datapoint_per_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, dict[str, object]] = {}

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        if definition.key.endswith("_open_interest"):
            persisted[definition.key] = {
                "asset": asset,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_timestamp": (
                    result.source_timestamp if isinstance(result, Ok) else None
                ),
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {
        "btc_open_interest",
        "eth_open_interest",
        "sol_open_interest",
        "bnb_open_interest",
    }
    assert {row["asset"] for row in persisted.values()} == {
        "BTC",
        "ETH",
        "SOL",
        "BNB",
    }
    assert all(row["status"] == "OK" for row in persisted.values())
    assert all(row["value"] is not None for row in persisted.values())
    assert all(
        row["source_timestamp"] == SOURCE_TIMESTAMP
        for row in persisted.values()
    )


def test_one_funding_history_failure_persists_error_and_other_assets_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, Result] = {}

    def fetch_funding_rate(asset: str) -> FundingRateResult:
        if asset == "SOL":
            return Error(reason=Reason.FETCH_FAILED, detail="forced funding failure")
        return _fetch_funding_rate(asset)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        if definition.key.endswith("_funding_rate"):
            persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=fetch_funding_rate,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert persisted["sol_funding_rate"] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced funding failure",
    )
    assert {
        key
        for key, result in persisted.items()
        if isinstance(result, Ok)
    } == {"btc_funding_rate", "eth_funding_rate", "bnb_funding_rate"}


def test_board_persistence_is_idempotent_per_registered_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: dict[tuple[str, str, str, datetime | None], int] = {}

    def upsert_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        source_timestamp = (
            result.source_timestamp
            if isinstance(result, (Ok, FundingRateOk, OpenInterestOk))
            else None
        )
        identity = (
            definition.key,
            asset,
            definition.vendor,
            source_timestamp,
        )
        return rows.setdefault(identity, len(rows) + 1)

    monkeypatch.setattr(pipeline, "persist_datapoint", upsert_datapoint)

    first_ids = run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]
    second_ids = run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(rows) == 52
    assert first_ids == second_ids


def test_database_holds_complete_board_with_failure_and_idempotent_identity(
    monkeypatch: pytest.MonkeyPatch,
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    failed_key = "btc_rsi"
    calculate = pipeline._calculate

    def fail_one_indicator(
        definition: IndicatorDefinition, bars: tuple[dict[str, float], ...]
    ) -> float:
        if definition.key == failed_key:
            raise ValueError("forced computation failure")
        return calculate(definition, bars)

    monkeypatch.setattr(pipeline, "_calculate", fail_one_indicator)

    first_ids = run_pipeline(postgres, fetcher=_full_board)
    second_ids = run_pipeline(postgres, fetcher=_full_board)
    rows = postgres.execute(
        """
        select indicator_key, asset, measured_on, value, status, reason,
               source_vendor, endpoint, source_field, fetched_at, source_timestamp
        from datapoints
        where id = any(%s)
        """,
        (list(second_ids),),
    ).fetchall()

    assert first_ids == second_ids
    assert len(rows) == 52
    failed = next(row for row in rows if row[0] == failed_key)
    assert failed[3:6] == (None, "ERROR", "FETCH_FAILED")
    assert failed[10] is None
    assert sum(row[4] == "OK" for row in rows) == 51
    assert all(row[1] == row[2] for row in rows)
    assert all(row[6] and row[7] and row[8] and row[9] for row in rows)
    assert all(
        row[10] == SOURCE_TIMESTAMP for row in rows if row[4] == "OK"
    )


def test_scheduled_ingestion_routes_the_full_board_through_run_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board = FullAssetRun(
        indicators={
            definition.key: Ok(1.0, SOURCE_TIMESTAMP)
            for definition in _board_definitions()
        },
        history={},
    )
    observed: list[FullAssetRun] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def persist_pipeline(
        connection: object,
        fetcher: Any,
    ) -> tuple[int, ...]:
        assert isinstance(connection, FakeConnection)
        result = fetcher()
        observed.append(result)
        return tuple(range(1, 53))

    monkeypatch.setattr(heartbeat.psycopg, "connect", lambda _: FakeConnection())
    monkeypatch.setattr(heartbeat, "run_all_assets", lambda: board)
    monkeypatch.setattr(heartbeat, "run_pipeline", persist_pipeline)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request)
        )
    )

    row_ids = heartbeat.run_ingestion(
        "postgresql://example.test/app",
        "https://hc-ping.com/check-id",
        heartbeat_client=client,
    )

    assert observed == [board]
    assert row_ids == tuple(range(1, 53))


@pytest.mark.integration
def test_live_full_board_run_persists_registry_row_count(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    run = run_all_assets()
    row_ids = run_pipeline(postgres, fetcher=lambda: run)
    definitions = _board_definitions()

    rows = postgres.execute(
        """
        select indicator_key, asset, measured_on, value, status, reason,
               source_vendor, endpoint, source_field, fetched_at, source_timestamp
        from datapoints
        where id = any(%s)
        """,
        (list(row_ids),),
    ).fetchall()

    assert len(definitions) == 52
    assert all(item.status == "AVAILABLE" for item in run.history.values())
    assert all(item.fetched_bars == 250 for item in run.history.values())
    assert all(
        isinstance(result, (Ok, FundingRateOk, OpenInterestOk))
        for result in run.indicators.values()
    )
    assert len(row_ids) == len(definitions)
    assert len(rows) == len(definitions)
    assert {row[0] for row in rows} == {definition.key for definition in definitions}
    assert sum(str(row[0]).endswith("_funding_rate") for row in rows) == 4
    assert sum(str(row[0]).endswith("_open_interest") for row in rows) == 4
    assert all(row[1] == row[2] for row in rows)
    assert all(row[6] and row[7] and row[8] and row[9] for row in rows)
    assert all(row[3] is not None and row[4:6] == ("OK", None) for row in rows)
    assert all(row[10] is not None for row in rows)
