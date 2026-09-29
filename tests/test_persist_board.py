from __future__ import annotations

import inspect
import math
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Self
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest import heartbeat, pipeline
from ingest.fetchers.alternative_me import AlternativeMeFearGreedOk
from ingest.fetchers.defillama_stablecoins import DefiLlamaStablecoinSupplyOk
from ingest.fetchers.fred import FredOk, FredResult, FredSeries
from ingest.fetchers.okx_derivatives import (
    FundingRateOk,
    LongShortRatioOk,
    OpenInterestOk,
    TakerRatioOk,
)
from ingest.fetchers.sosovalue import SosoValueEtfFlowOk, SosoValueEtfFlowResult
from ingest.pipeline import (
    FetchedBars,
    FundingRateResult,
    LongShortRatioResult,
    OpenInterestResult,
    TakerRatioResult,
    Venue,
    run_all_assets,
    run_pipeline,
    run_scheduled_board,
    run_sol_active_addresses,
)
from ingest.registry import IndicatorDefinition, load_registry
from ingest.status import Error, Ok, Reason, Result, Stale, Unavailable

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"
DATABASE_URL = "postgresql://example.test/app"
HEARTBEAT_URL = "https://hc-ping.com/check-id"
SOURCE_TIMESTAMP = datetime(2026, 9, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def freeze_pipeline_freshness_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "_utc_now", lambda: SOURCE_TIMESTAMP)


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


def _fetch_long_short_ratio(asset: str) -> LongShortRatioResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return LongShortRatioOk(
        value=1.0 + offset / 10,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def _fetch_taker_ratio(asset: str) -> TakerRatioResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return TakerRatioOk(
        value=1.0 + offset / 10,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def _fetch_mvrv(asset: str, rate_limiter: object | None = None) -> Result:
    offset = {"BTC": 1.0, "ETH": 2.0, "BNB": 3.0}[asset]
    return Ok(value=offset + 1.5, source_timestamp=SOURCE_TIMESTAMP)


def _fetch_active_addresses(asset: str, rate_limiter: object | None = None) -> Result:
    offset = {"BTC": 1_000.0, "ETH": 2_000.0, "BNB": 3_000.0, "SOL": 4_000.0}[
        asset
    ]
    return Ok(value=offset, source_timestamp=SOURCE_TIMESTAMP)


def _fetch_exchange_flow(asset: str, rate_limiter: object | None = None) -> Result:
    offset = {"BTC": 10.0, "ETH": 20.0}[asset]
    return Ok(value=offset, source_timestamp=SOURCE_TIMESTAMP)


def _fetch_staking(asset: str) -> Result:
    assert asset == "SOL"
    return Ok(value=390_383_623.78255165, source_timestamp=SOURCE_TIMESTAMP)


def _fetch_fred(series: FredSeries) -> FredResult:
    return FredOk(
        value={
            "VIXCLS": 18.0,
            "DFF": 4.33,
            "T10Y2Y": -0.12,
            "DFII10": 1.88,
            "DTWEXBGS": 120.0,
            "CPIAUCSL": 320.0,
            "M2SL": 22_000.0,
        }[series.series_id],
        source_timestamp=SOURCE_TIMESTAMP,
        reference_period=SOURCE_TIMESTAMP.date().isoformat(),
        published_at=SOURCE_TIMESTAMP,
        source_field=series.source_field,
    )


def _fetch_etf_flow(asset: str) -> SosoValueEtfFlowResult:
    offset = {"BTC": 100.0, "ETH": 200.0, "SOL": 300.0}[asset]
    return SosoValueEtfFlowOk(
        value=offset,
        source_timestamp=SOURCE_TIMESTAMP,
        reference_period=SOURCE_TIMESTAMP.date().isoformat(),
        published_at=SOURCE_TIMESTAMP,
    )


def _fetch_stablecoin_supply(asset: str) -> pipeline.DefiLlamaStablecoinSupplyResult:
    offset = {"ETH": 10_000.0, "SOL": 20_000.0, "BNB": 30_000.0}[asset]
    return DefiLlamaStablecoinSupplyOk(
        value=offset,
        source_timestamp=SOURCE_TIMESTAMP,
        reference_period="current",
        published_at=SOURCE_TIMESTAMP,
        chain={"ETH": "Ethereum", "SOL": "Solana", "BNB": "BSC"}[asset],
    )


def _fetch_fear_greed() -> pipeline.AlternativeMeFearGreedResult:
    return AlternativeMeFearGreedOk(
        value=70,
        source_timestamp=SOURCE_TIMESTAMP,
        reference_period=SOURCE_TIMESTAMP.date().isoformat(),
        published_at=SOURCE_TIMESTAMP,
        value_classification="Greed",
    )


def _full_board() -> pipeline.FullAssetRun:
    return run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )


def _tier_board(tier: pipeline.CadenceTier) -> pipeline.FullAssetRun:
    return run_all_assets(
        tier=tier,
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )


def _board_definitions() -> tuple[IndicatorDefinition, ...]:
    return tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_candle"
        or definition.response_model == "okx_funding_rate_history"
        or definition.response_model == "okx_open_interest"
        or definition.response_model == "okx_long_short_ratio"
        or definition.response_model == "okx_taker_volume"
        or definition.response_model == "coinmetrics_asset_metrics"
        or definition.response_model == "solana_get_block"
        or definition.response_model == "validators_app_validators"
        or definition.response_model == "fred_series_observations"
        or definition.response_model == "sosovalue_etf_summary_history"
        or definition.response_model == "defillama_stablecoinchains"
        or definition.response_model == "alternative_me_fear_greed"
    )


def _expected_rows(definitions: tuple[IndicatorDefinition, ...]) -> int:
    return sum(len(definition.definable_for) for definition in definitions)


def _expected_row_identities(
    definitions: tuple[IndicatorDefinition, ...],
) -> set[tuple[str, str]]:
    return {
        (definition.key, asset)
        for definition in definitions
        for asset in definition.definable_for
    }


def _expected_run_keys(definitions: tuple[IndicatorDefinition, ...]) -> set[str]:
    return {
        (
            definition.key
            if definition.definable_for == (asset,)
            else f"{definition.key}\x1f{asset}"
        )
        for definition in definitions
        for asset in definition.definable_for
    }


def _scheduled_board_definitions() -> tuple[IndicatorDefinition, ...]:
    return tuple(
        definition
        for definition in _board_definitions()
        if definition.key != pipeline.SOL_ACTIVE_ADDRESSES_KEY
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
        **_: object,
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
    assert len(definitions) == 84
    assert len(row_ids) == _expected_rows(definitions)
    assert len(persisted) == _expected_rows(definitions)
    assert {row["indicator_key"] for row in persisted} == {
        definition.key for definition in definitions
    }


@pytest.mark.parametrize(
    ("tier", "expected_count"),
    (("fast", 12), ("medium", 4), ("daily", 71)),
)
def test_tier_run_persists_only_registry_entries_for_that_cadence(
    monkeypatch: pytest.MonkeyPatch,
    tier: pipeline.CadenceTier,
    expected_count: int,
) -> None:
    persisted: list[str] = []

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted.append(definition.key)
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    row_ids = run_pipeline(  # type: ignore[arg-type]
        object(), fetcher=lambda: _tier_board(tier)
    )

    expected = {
        definition.key
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds
        == pipeline.TIER_INTERVAL_SECONDS[tier]
    }
    expected_definitions = tuple(
        definition
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds
        == pipeline.TIER_INTERVAL_SECONDS[tier]
    )
    assert _expected_rows(expected_definitions) == expected_count
    assert len(row_ids) == expected_count
    assert set(persisted) == expected


def test_tier_runs_union_to_the_scheduled_registry_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted_by_tier: dict[str, list[tuple[str, str]]] = {
        "fast": [],
        "medium": [],
        "daily": [],
    }
    active_tier = ""

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted_by_tier[active_tier].append((definition.key, asset))
        return sum(len(keys) for keys in persisted_by_tier.values())

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    for tier in ("fast", "medium", "daily"):
        active_tier = tier
        run_pipeline(  # type: ignore[arg-type]
            object(), fetcher=lambda tier=tier: _tier_board(tier)
        )

    flattened = [row for persisted in persisted_by_tier.values() for row in persisted]
    definitions = tuple(
        definition
        for definition in _board_definitions()
        if definition.key != pipeline.SOL_ACTIVE_ADDRESSES_KEY
    )
    assert set(flattened) == _expected_row_identities(definitions)
    assert len(flattened) == len(set(flattened)) == _expected_rows(definitions)


def test_adversarial_fast_tier_missed_window_reads_stale_within_450_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_at = SOURCE_TIMESTAMP + timedelta(seconds=451)
    persisted: dict[str, Result] = {}

    def fetch_open_interest(asset: str) -> OpenInterestResult:
        source_timestamp = (
            read_at - timedelta(seconds=451)
            if asset == "BTC"
            else read_at - timedelta(seconds=1)
        )
        return OpenInterestOk(value=1_000_000.0, source_timestamp=source_timestamp)

    def fetch_long_short_ratio(asset: str) -> LongShortRatioResult:
        return LongShortRatioOk(
            value=1.1, source_timestamp=read_at - timedelta(seconds=1)
        )

    def fetch_taker_ratio(asset: str) -> TakerRatioResult:
        return TakerRatioOk(value=1.1, source_timestamp=read_at - timedelta(seconds=1))

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "_utc_now", lambda: read_at)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    row_ids = run_pipeline(
        object(),  # type: ignore[arg-type]
        fetcher=lambda: run_all_assets(
            tier="fast",
            fetch_open_interest=fetch_open_interest,
            fetch_long_short_ratio=fetch_long_short_ratio,
            fetch_taker_ratio=fetch_taker_ratio,
        ),
    )

    definition = next(
        entry for entry in load_registry().root if entry.key == "btc_open_interest"
    )
    affected = persisted["btc_open_interest"]
    assert definition.expected_update_interval_seconds == 300
    assert definition.freshness_warn_seconds == 450
    assert definition.freshness_stale_seconds == 600
    assert len(row_ids) == 12
    assert isinstance(affected, Stale)
    assert affected.source_timestamp == read_at - timedelta(seconds=451)
    assert persisted["eth_open_interest"].status == "OK"
    assert persisted["btc_long_short_ratio"].status == "OK"
    assert persisted["btc_taker_ratio"].status == "OK"


def test_adversarial_full_cycle_reconciles_all_75_registry_rows_once_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted_by_run: dict[str, list[tuple[str, str]]] = {
        "fast": [],
        "medium": [],
        "daily": [],
        "sol_active_addresses": [],
    }
    active_run = ""

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted_by_run[active_run].append((definition.key, asset))
        return sum(len(keys) for keys in persisted_by_run.values())

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    for tier in ("fast", "medium", "daily"):
        active_run = tier
        run_pipeline(  # type: ignore[arg-type]
            object(), fetcher=lambda tier=tier: _tier_board(tier)
        )
    active_run = "sol_active_addresses"
    run_pipeline(  # type: ignore[arg-type]
        object(), fetcher=run_sol_active_addresses
    )

    flattened = [row for persisted in persisted_by_run.values() for row in persisted]
    assert len(_board_definitions()) == 84
    assert len(persisted_by_run["fast"]) == 12
    assert len(persisted_by_run["medium"]) == 4
    assert len(persisted_by_run["daily"]) == 71
    assert persisted_by_run["sol_active_addresses"] == [
        (pipeline.SOL_ACTIVE_ADDRESSES_KEY, "SOL")
    ]
    assert set(flattened) == _expected_row_identities(_board_definitions())
    assert len(flattened) == len(set(flattened)) == _expected_rows(
        _board_definitions()
    )


def test_scheduled_daily_tier_keeps_existing_sol_active_addresses_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fetch_scheduled_active_addresses(
        asset: str, rate_limiter: object | None = None
    ) -> Result:
        assert asset != "SOL"
        return _fetch_active_addresses(asset, rate_limiter)

    monkeypatch.setattr(pipeline, "_fetch_asset_bars", _fetch_bars)
    monkeypatch.setattr(pipeline, "_fetch_asset_funding_rate", _fetch_funding_rate)
    monkeypatch.setattr(pipeline, "_fetch_asset_open_interest", _fetch_open_interest)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_long_short_ratio", _fetch_long_short_ratio
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_taker_ratio", _fetch_taker_ratio)
    monkeypatch.setattr(pipeline, "_fetch_asset_mvrv", _fetch_mvrv)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_active_addresses", fetch_scheduled_active_addresses
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_exchange_flow", _fetch_exchange_flow)
    monkeypatch.setattr(pipeline, "_fetch_asset_staking", _fetch_staking)
    monkeypatch.setattr(pipeline, "_fetch_fred_series", _fetch_fred)
    monkeypatch.setattr(pipeline, "_fetch_etf_net_flow", _fetch_etf_flow)
    monkeypatch.setattr(pipeline, "_fetch_stablecoin_supply", _fetch_stablecoin_supply)
    monkeypatch.setattr(pipeline, "_fetch_fear_greed_index", _fetch_fear_greed)

    run = run_scheduled_board(tier="daily")
    expected_definitions = tuple(
        definition
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds == 86400
        and definition.key != pipeline.SOL_ACTIVE_ADDRESSES_KEY
    )

    assert _expected_rows(expected_definitions) == 71
    assert set(run.indicators) == _expected_run_keys(expected_definitions)


def test_no_tier_argument_preserves_full_registry_board_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[str] = []

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted.append(definition.key)
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    row_ids = run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(row_ids) == _expected_rows(_board_definitions())
    assert set(persisted) == {definition.key for definition in _board_definitions()}


def test_persist_board_has_one_path_for_technical_derivatives_onchain_macro_and_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = inspect.getsource(pipeline.persist_board)
    assert "_active_addresses" not in source
    assert "_mvrv" not in source
    assert "_exchange_flow" not in source
    assert "_staking" not in source
    assert "fred_series_observations" not in source
    assert "sosovalue_etf_summary_history" not in source
    assert "defillama_stablecoinchains" not in source

    persisted: dict[tuple[str, str], Result] = {}

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted[(definition.key, asset)] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    row_ids = pipeline.persist_board(
        object(),  # type: ignore[arg-type]
        pipeline.FullAssetRun(
            indicators={
                "btc_rsi": Ok(value=42.0, source_timestamp=SOURCE_TIMESTAMP),
                "btc_funding_rate": FundingRateOk(
                    value=0.0001,
                    source_timestamp=SOURCE_TIMESTAMP,
                    source_field="runtime funding source field",
                ),
                "btc_mvrv": Ok(value=2.5, source_timestamp=SOURCE_TIMESTAMP),
                "macro_vixcls": _fetch_fred(FredSeries("VIXCLS")),
                "spot_etf_net_flow\x1fBTC": _fetch_etf_flow("BTC"),
                "stablecoin_supply\x1fETH": _fetch_stablecoin_supply("ETH"),
                "fear_greed_index": _fetch_fear_greed(),
            },
            history={},
        ),
    )

    assert row_ids == (1, 2, 3, 4, 5, 6, 7)
    assert set(persisted) == {
        ("btc_rsi", "BTC"),
        ("btc_funding_rate", "BTC"),
        ("btc_mvrv", "BTC"),
        ("macro_vixcls", "MACRO"),
        ("spot_etf_net_flow", "BTC"),
        ("stablecoin_supply", "ETH"),
        ("fear_greed_index", "MACRO"),
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
        **_: object,
    ) -> int:
        persisted.append(
            {
                "source_vendor": definition.vendor,
                "endpoint": definition.endpoint,
                "source_field": definition.source_field,
                "source_timestamp": (
                    result.source_timestamp
                    if isinstance(
                        result,
                        (
                            Ok,
                            FundingRateOk,
                            OpenInterestOk,
                            LongShortRatioOk,
                            TakerRatioOk,
                        ),
                    )
                    else None
                ),
                "measured_on": measured_on,
                "asset": asset,
            }
        )
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(persisted) == _expected_rows(_board_definitions())
    assert {row["source_vendor"] for row in persisted if row["source_vendor"]} == {
        "okx",
        "coinmetrics",
        "helius",
        "validators_app",
        "fred",
        "sosovalue",
        "defillama",
        "alternative.me",
    }
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
        **_: object,
    ) -> int:
        persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "_calculate", fail_one_indicator)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert len(persisted) == len(_board_definitions())
    assert persisted[failed_key] == Error(
        reason=Reason.FETCH_FAILED,
        detail="btc_rsi computation failed: forced computation failure",
    )
    assert sum(isinstance(result, Ok) for result in persisted.values()) == (
        len(_board_definitions()) - 1
    )


def test_one_derivatives_fetch_failure_persists_error_and_other_cells_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, Result] = {}

    def fetch_long_short_ratio(asset: str) -> LongShortRatioResult:
        if asset == "SOL":
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="forced long/short failure",
            )
        return _fetch_long_short_ratio(asset)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert len(persisted) == len(_board_definitions())
    assert persisted["sol_long_short_ratio"] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced long/short failure",
    )
    assert sum(isinstance(result, Ok) for result in persisted.values()) == (
        len(_board_definitions()) - 1
    )


def test_full_run_persists_one_mvrv_datapoint_per_btc_eth_bnb(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_mvrv"):
            persisted[definition.key] = {
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_vendor": definition.vendor,
                "source_timestamp": (
                    result.source_timestamp if isinstance(result, Ok) else None
                ),
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {"btc_mvrv", "eth_mvrv", "bnb_mvrv"}
    assert {row["asset"] for row in persisted.values()} == {"BTC", "ETH", "BNB"}
    assert all(row["measured_on"] == row["asset"] for row in persisted.values())
    assert all(row["status"] == "OK" for row in persisted.values())
    assert all(row["value"] is not None for row in persisted.values())
    assert all(row["source_vendor"] == "coinmetrics" for row in persisted.values())
    assert all(
        row["source_timestamp"] == SOURCE_TIMESTAMP
        for row in persisted.values()
    )


def test_one_mvrv_fetch_failure_persists_error_and_other_assets_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, Result] = {}

    def fetch_mvrv(asset: str) -> Result:
        if asset == "ETH":
            return Error(reason=Reason.FETCH_FAILED, detail="forced ETH MVRV failure")
        return _fetch_mvrv(asset)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        if definition.key.endswith("_mvrv"):
            persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert persisted["eth_mvrv"] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced ETH MVRV failure",
    )
    assert {
        key
        for key, result in persisted.items()
        if isinstance(result, Ok)
    } == {"btc_mvrv", "bnb_mvrv"}


def test_full_run_persists_one_active_addresses_datapoint_per_btc_eth_bnb(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_active_addresses"):
            persisted[definition.key] = {
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_vendor": definition.vendor,
                "source_timestamp": (
                    result.source_timestamp if isinstance(result, Ok) else None
                ),
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {
        "btc_active_addresses",
        "eth_active_addresses",
        "bnb_active_addresses",
        "sol_active_addresses",
    }
    assert {row["asset"] for row in persisted.values()} == {
        "BTC",
        "ETH",
        "BNB",
        "SOL",
    }
    assert all(row["measured_on"] == row["asset"] for row in persisted.values())
    assert all(row["status"] == "OK" for row in persisted.values())
    assert all(row["value"] is not None for row in persisted.values())
    assert {row["source_vendor"] for row in persisted.values()} == {
        "coinmetrics",
        "helius",
    }
    assert all(
        row["source_timestamp"] == SOURCE_TIMESTAMP for row in persisted.values()
    )


def test_one_active_addresses_fetch_failure_persists_error_and_other_assets_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, Result] = {}

    def fetch_active_addresses(asset: str) -> Result:
        if asset == "ETH":
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="forced ETH active-addresses failure",
            )
        return _fetch_active_addresses(asset)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        if definition.key.endswith("_active_addresses"):
            persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert persisted["eth_active_addresses"] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced ETH active-addresses failure",
    )
    assert {key for key, result in persisted.items() if isinstance(result, Ok)} == {
        "btc_active_addresses",
        "bnb_active_addresses",
        "sol_active_addresses",
    }


def test_one_onchain_fetch_failure_persists_error_and_all_other_categories_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, Result] = {}

    def fetch_mvrv(asset: str) -> Result:
        if asset == "ETH":
            return Error(reason=Reason.FETCH_FAILED, detail="forced ETH MVRV failure")
        return _fetch_mvrv(asset)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert persisted["eth_mvrv"] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced ETH MVRV failure",
    )
    assert isinstance(persisted["btc_rsi"], Ok)
    assert isinstance(persisted["btc_funding_rate"], Ok)
    assert isinstance(persisted["btc_active_addresses"], Ok)
    assert isinstance(persisted["sol_staking"], Ok)
    assert len(persisted) == len(_board_definitions())


def test_one_macro_flow_fetch_failure_persists_error_and_all_categories_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[tuple[str, str], Result] = {}

    def fetch_fred(series: FredSeries) -> FredResult:
        if series.series_id == "DFF":
            return Error(reason=Reason.FETCH_FAILED, detail="forced FRED failure")
        return _fetch_fred(series)

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        persisted[(definition.key, asset)] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=_fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
    )

    run_pipeline(object(), fetcher=lambda: run)  # type: ignore[arg-type]

    assert persisted[("macro_dff", "MACRO")] == Error(
        reason=Reason.FETCH_FAILED,
        detail="forced FRED failure",
    )
    assert isinstance(persisted[("btc_rsi", "BTC")], Ok)
    assert isinstance(persisted[("btc_funding_rate", "BTC")], Ok)
    assert isinstance(persisted[("btc_mvrv", "BTC")], Ok)
    assert isinstance(persisted[("spot_etf_net_flow", "BTC")], Ok)
    assert isinstance(persisted[("stablecoin_supply", "ETH")], Ok)
    assert isinstance(persisted[("fear_greed_index", "MACRO")], Ok)
    assert len(persisted) == _expected_rows(_board_definitions())


def test_full_run_persists_one_exchange_flow_datapoint_per_btc_eth(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_exchange_flow"):
            persisted[definition.key] = {
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_vendor": definition.vendor,
                "source_timestamp": (
                    result.source_timestamp if isinstance(result, Ok) else None
                ),
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {"btc_exchange_flow", "eth_exchange_flow"}
    assert {row["asset"] for row in persisted.values()} == {"BTC", "ETH"}
    assert all(row["measured_on"] == row["asset"] for row in persisted.values())
    assert all(row["status"] == "OK" for row in persisted.values())
    assert all(row["value"] is not None for row in persisted.values())
    assert all(row["source_vendor"] == "coinmetrics" for row in persisted.values())
    assert all(
        row["source_timestamp"] == SOURCE_TIMESTAMP for row in persisted.values()
    )


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
        **_: object,
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


def test_full_run_persists_fear_greed_with_disclosure_and_reference_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: dict[str, object] = {}

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        reference_period: str | None = None,
        published_at: datetime | None = None,
    ) -> int:
        if definition.key == "fear_greed_index":
            persisted.update(
                {
                    "asset": asset,
                    "measured_on": measured_on,
                    "status": result.status,
                    "value": result.value if isinstance(result, Ok) else None,
                    "source_vendor": definition.vendor,
                    "source_field": definition.source_field,
                    "source_timestamp": (
                        result.source_timestamp if isinstance(result, Ok) else None
                    ),
                    "reference_period": reference_period,
                    "published_at": published_at,
                }
            )
        return 1

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert persisted["asset"] == "MACRO"
    assert persisted["measured_on"] == "MACRO"
    assert persisted["status"] == "OK"
    assert persisted["value"] == 70.0
    assert persisted["source_vendor"] == "alternative.me"
    assert persisted["source_timestamp"] == SOURCE_TIMESTAMP
    assert persisted["reference_period"] == SOURCE_TIMESTAMP.date().isoformat()
    assert persisted["published_at"] == SOURCE_TIMESTAMP
    assert "six-weight composite" in str(persisted["source_field"])
    assert "surveys 15% currently paused" in str(persisted["source_field"])
    assert "Data provided by alternative.me" in str(persisted["source_field"])


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
        **_: object,
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


def test_full_run_persists_one_staking_datapoint_for_sol(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_staking"):
            persisted[definition.key] = {
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
                "value": result.value if isinstance(result, Ok) else None,
                "source_vendor": definition.vendor,
                "source_timestamp": (
                    result.source_timestamp if isinstance(result, Ok) else None
                ),
            }
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    run_pipeline(object(), fetcher=_full_board)  # type: ignore[arg-type]

    assert set(persisted) == {"sol_staking"}
    row = persisted["sol_staking"]
    assert row["asset"] == row["measured_on"] == "SOL"
    assert row["status"] == "OK"
    assert row["value"] == 390_383_623.78255165
    assert row["source_vendor"] == "validators_app"
    assert row["source_timestamp"] == SOURCE_TIMESTAMP


def test_full_run_persists_one_long_short_ratio_datapoint_per_asset(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_long_short_ratio"):
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
        "btc_long_short_ratio",
        "eth_long_short_ratio",
        "sol_long_short_ratio",
        "bnb_long_short_ratio",
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
        row["source_timestamp"] == SOURCE_TIMESTAMP for row in persisted.values()
    )


def test_full_run_persists_one_taker_ratio_datapoint_per_asset(
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_taker_ratio"):
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
        "btc_taker_ratio",
        "eth_taker_ratio",
        "sol_taker_ratio",
        "bnb_taker_ratio",
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
        row["source_timestamp"] == SOURCE_TIMESTAMP for row in persisted.values()
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
        **_: object,
    ) -> int:
        if definition.key.endswith("_funding_rate"):
            persisted[definition.key] = result
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    run = run_all_assets(
        fetch_bars=_fetch_bars,
        fetch_funding_rate=fetch_funding_rate,
        fetch_open_interest=_fetch_open_interest,
        fetch_long_short_ratio=_fetch_long_short_ratio,
        fetch_taker_ratio=_fetch_taker_ratio,
        fetch_mvrv=_fetch_mvrv,
        fetch_active_addresses=_fetch_active_addresses,
        fetch_exchange_flow=_fetch_exchange_flow,
        fetch_staking=_fetch_staking,
        fetch_fred=_fetch_fred,
        fetch_etf_flow=_fetch_etf_flow,
        fetch_stablecoin_supply=_fetch_stablecoin_supply,
        fetch_fear_greed=_fetch_fear_greed,
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
        **_: object,
    ) -> int:
        source_timestamp = (
            result.source_timestamp
            if isinstance(
                result,
                (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
            )
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

    assert len(rows) == _expected_rows(_board_definitions())
    assert first_ids == second_ids


@pytest.mark.integration
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
    assert len(rows) == _expected_rows(_board_definitions())
    failed = next(row for row in rows if row[0] == failed_key)
    assert failed[3:6] == (None, "ERROR", "FETCH_FAILED")
    assert failed[10] is None
    assert sum(row[4] == "OK" for row in rows) == (
        _expected_rows(_board_definitions()) - 1
    )
    assert all(row[1] == row[2] for row in rows)
    assert all(row[6] and row[7] and row[8] and row[9] for row in rows)
    assert all(
        row[10] == SOURCE_TIMESTAMP for row in rows if row[4] == "OK"
    )


def test_scheduled_entry_point_persists_board_without_sol_active_addresses_and_pings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []
    connected_to: list[str] = []
    pinged: list[str] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def connect(database_url: str) -> FakeConnection:
        connected_to.append(database_url)
        return FakeConnection()

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        assert isinstance(connection, FakeConnection)
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    def record_ping(url: str, *, timeout: int) -> httpx.Response:
        pinged.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    def fetch_scheduled_active_addresses(
        asset: str, rate_limiter: object | None = None
    ) -> Result:
        assert asset != "SOL"
        return _fetch_active_addresses(asset, rate_limiter)

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat.psycopg, "connect", connect)
    monkeypatch.setattr(heartbeat.httpx, "get", record_ping)
    monkeypatch.setattr(pipeline, "_fetch_asset_bars", _fetch_bars)
    monkeypatch.setattr(pipeline, "_fetch_asset_funding_rate", _fetch_funding_rate)
    monkeypatch.setattr(pipeline, "_fetch_asset_open_interest", _fetch_open_interest)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_long_short_ratio", _fetch_long_short_ratio
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_taker_ratio", _fetch_taker_ratio)
    monkeypatch.setattr(pipeline, "_fetch_asset_mvrv", _fetch_mvrv)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_active_addresses", fetch_scheduled_active_addresses
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_exchange_flow", _fetch_exchange_flow)
    monkeypatch.setattr(pipeline, "_fetch_asset_staking", _fetch_staking)
    monkeypatch.setattr(pipeline, "_fetch_fred_series", _fetch_fred)
    monkeypatch.setattr(pipeline, "_fetch_etf_net_flow", _fetch_etf_flow)
    monkeypatch.setattr(pipeline, "_fetch_stablecoin_supply", _fetch_stablecoin_supply)
    monkeypatch.setattr(pipeline, "_fetch_fear_greed_index", _fetch_fear_greed)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    heartbeat.main()

    definitions = _scheduled_board_definitions()
    assert connected_to == [DATABASE_URL]
    assert pinged == [HEARTBEAT_URL]
    assert len(_board_definitions()) == 84
    assert _expected_rows(definitions) == 87
    assert len(persisted) == _expected_rows(definitions)
    assert {row["indicator_key"] for row in persisted} == {
        definition.key for definition in definitions
    }
    assert pipeline.SOL_ACTIVE_ADDRESSES_KEY not in {
        row["indicator_key"] for row in persisted
    }
    assert (
        sum(str(row["indicator_key"]).endswith("_funding_rate") for row in persisted)
        == 4
    )
    assert (
        sum(str(row["indicator_key"]).endswith("_open_interest") for row in persisted)
        == 4
    )
    assert (
        sum(
            str(row["indicator_key"]).endswith("_long_short_ratio")
            for row in persisted
        )
        == 4
    )
    assert (
        sum(str(row["indicator_key"]).endswith("_taker_ratio") for row in persisted)
        == 4
    )
    assert sum(str(row["indicator_key"]).endswith("_mvrv") for row in persisted) == 3
    assert (
        sum(
            str(row["indicator_key"]).endswith("_active_addresses") for row in persisted
        )
        == 3
    )
    assert (
        sum(str(row["indicator_key"]).endswith("_exchange_flow") for row in persisted)
        == 2
    )
    assert sum(str(row["indicator_key"]).endswith("_staking") for row in persisted) == 1
    assert sum(str(row["indicator_key"]).startswith("macro_") for row in persisted) == 7
    assert sum(row["indicator_key"] == "spot_etf_net_flow" for row in persisted) == 3
    assert sum(row["indicator_key"] == "stablecoin_supply" for row in persisted) == 3
    assert sum(row["indicator_key"] == "fear_greed_index" for row in persisted) == 1
    assert all(row["asset"] == row["measured_on"] for row in persisted)


def test_daily_tier_entry_point_persists_only_daily_board_rows_and_pings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []
    connected_to: list[str] = []
    pinged: list[str] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def connect(database_url: str) -> FakeConnection:
        connected_to.append(database_url)
        return FakeConnection()

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        assert isinstance(connection, FakeConnection)
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    def record_ping(url: str, *, timeout: int) -> httpx.Response:
        pinged.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    def fetch_scheduled_active_addresses(
        asset: str, rate_limiter: object | None = None
    ) -> Result:
        assert asset != "SOL"
        return _fetch_active_addresses(asset, rate_limiter)

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat.psycopg, "connect", connect)
    monkeypatch.setattr(heartbeat.httpx, "get", record_ping)
    monkeypatch.setattr(pipeline, "_fetch_asset_bars", _fetch_bars)
    monkeypatch.setattr(pipeline, "_fetch_asset_funding_rate", _fetch_funding_rate)
    monkeypatch.setattr(pipeline, "_fetch_asset_open_interest", _fetch_open_interest)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_long_short_ratio", _fetch_long_short_ratio
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_taker_ratio", _fetch_taker_ratio)
    monkeypatch.setattr(pipeline, "_fetch_asset_mvrv", _fetch_mvrv)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_active_addresses", fetch_scheduled_active_addresses
    )
    monkeypatch.setattr(pipeline, "_fetch_asset_exchange_flow", _fetch_exchange_flow)
    monkeypatch.setattr(pipeline, "_fetch_asset_staking", _fetch_staking)
    monkeypatch.setattr(pipeline, "_fetch_fred_series", _fetch_fred)
    monkeypatch.setattr(pipeline, "_fetch_etf_net_flow", _fetch_etf_flow)
    monkeypatch.setattr(pipeline, "_fetch_stablecoin_supply", _fetch_stablecoin_supply)
    monkeypatch.setattr(pipeline, "_fetch_fear_greed_index", _fetch_fear_greed)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    heartbeat.main(["--tier", "daily"])

    expected_definitions = tuple(
        definition
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds == 86400
        and definition.key != pipeline.SOL_ACTIVE_ADDRESSES_KEY
    )
    assert connected_to == [DATABASE_URL]
    assert pinged == [HEARTBEAT_URL]
    assert _expected_rows(expected_definitions) == 71
    assert len(persisted) == _expected_rows(expected_definitions)
    assert {row["indicator_key"] for row in persisted} == {
        definition.key for definition in expected_definitions
    }
    assert pipeline.SOL_ACTIVE_ADDRESSES_KEY not in {
        row["indicator_key"] for row in persisted
    }
    assert sum(str(row["indicator_key"]).startswith("macro_") for row in persisted) == 7
    assert sum(row["indicator_key"] == "spot_etf_net_flow" for row in persisted) == 3
    assert sum(row["indicator_key"] == "stablecoin_supply" for row in persisted) == 3
    assert sum(row["indicator_key"] == "fear_greed_index" for row in persisted) == 1
    assert all(row["status"] == "OK" for row in persisted)
    assert all(row["asset"] == row["measured_on"] for row in persisted)


def test_medium_tier_entry_point_persists_only_medium_board_rows_and_pings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []
    connected_to: list[str] = []
    pinged: list[str] = []
    fetched_funding_for: list[str] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def connect(database_url: str) -> FakeConnection:
        connected_to.append(database_url)
        return FakeConnection()

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        assert isinstance(connection, FakeConnection)
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    def record_ping(url: str, *, timeout: int) -> httpx.Response:
        pinged.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    def fetch_funding_rate(asset: str) -> FundingRateResult:
        fetched_funding_for.append(asset)
        return _fetch_funding_rate(asset)

    def unexpected_fetch(*args: object, **kwargs: object) -> Result:
        raise AssertionError("medium tier should fetch only funding-rate rows")

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat.psycopg, "connect", connect)
    monkeypatch.setattr(heartbeat.httpx, "get", record_ping)
    monkeypatch.setattr(pipeline, "_fetch_asset_bars", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_funding_rate", fetch_funding_rate)
    monkeypatch.setattr(pipeline, "_fetch_asset_open_interest", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_long_short_ratio", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_taker_ratio", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_mvrv", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_active_addresses", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_exchange_flow", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_staking", unexpected_fetch)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    heartbeat.main(["--tier", "medium"])

    expected = {
        definition.key
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds == 28800
    }
    assert connected_to == [DATABASE_URL]
    assert pinged == [HEARTBEAT_URL]
    assert len(expected) == 4
    assert len(persisted) == 4
    assert {row["indicator_key"] for row in persisted} == expected
    assert {row["asset"] for row in persisted} == {"BTC", "ETH", "SOL", "BNB"}
    assert sorted(fetched_funding_for) == ["BNB", "BTC", "ETH", "SOL"]
    assert all(str(row["indicator_key"]).endswith("_funding_rate") for row in persisted)
    assert all(row["status"] == "OK" for row in persisted)
    assert all(row["asset"] == row["measured_on"] for row in persisted)


def test_fast_tier_entry_point_persists_only_fast_board_rows_and_pings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []
    connected_to: list[str] = []
    pinged: list[str] = []
    fetched_open_interest_for: list[str] = []
    fetched_long_short_for: list[str] = []
    fetched_taker_for: list[str] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def connect(database_url: str) -> FakeConnection:
        connected_to.append(database_url)
        return FakeConnection()

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        assert isinstance(connection, FakeConnection)
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    def record_ping(url: str, *, timeout: int) -> httpx.Response:
        pinged.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    def fetch_open_interest(asset: str) -> OpenInterestResult:
        fetched_open_interest_for.append(asset)
        return _fetch_open_interest(asset)

    def fetch_long_short_ratio(asset: str) -> LongShortRatioResult:
        fetched_long_short_for.append(asset)
        return _fetch_long_short_ratio(asset)

    def fetch_taker_ratio(asset: str) -> TakerRatioResult:
        fetched_taker_for.append(asset)
        return _fetch_taker_ratio(asset)

    def unexpected_fetch(*args: object, **kwargs: object) -> Result:
        raise AssertionError("fast tier should fetch only fast derivatives rows")

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat.psycopg, "connect", connect)
    monkeypatch.setattr(heartbeat.httpx, "get", record_ping)
    monkeypatch.setattr(pipeline, "_fetch_asset_bars", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_funding_rate", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_open_interest", fetch_open_interest)
    monkeypatch.setattr(pipeline, "_fetch_asset_long_short_ratio", fetch_long_short_ratio)
    monkeypatch.setattr(pipeline, "_fetch_asset_taker_ratio", fetch_taker_ratio)
    monkeypatch.setattr(pipeline, "_fetch_asset_mvrv", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_active_addresses", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_exchange_flow", unexpected_fetch)
    monkeypatch.setattr(pipeline, "_fetch_asset_staking", unexpected_fetch)
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    heartbeat.main(["--tier", "fast"])

    expected = {
        definition.key
        for definition in _board_definitions()
        if definition.expected_update_interval_seconds == 300
    }
    assert connected_to == [DATABASE_URL]
    assert pinged == [HEARTBEAT_URL]
    assert len(expected) == 12
    assert len(persisted) == 12
    assert {row["indicator_key"] for row in persisted} == expected
    assert {row["asset"] for row in persisted} == {"BTC", "ETH", "SOL", "BNB"}
    assert sorted(fetched_open_interest_for) == ["BNB", "BTC", "ETH", "SOL"]
    assert sorted(fetched_long_short_for) == ["BNB", "BTC", "ETH", "SOL"]
    assert sorted(fetched_taker_for) == ["BNB", "BTC", "ETH", "SOL"]
    assert all(
        str(row["indicator_key"]).endswith(
            ("_open_interest", "_long_short_ratio", "_taker_ratio")
        )
        for row in persisted
    )
    assert all(row["status"] == "OK" for row in persisted)
    assert all(row["asset"] == row["measured_on"] for row in persisted)


def test_sol_active_addresses_entry_point_persists_only_that_cell_and_pings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[dict[str, object]] = []
    connected_to: list[str] = []
    pinged: list[str] = []

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def connect(database_url: str) -> FakeConnection:
        connected_to.append(database_url)
        return FakeConnection()

    def record_datapoint(
        connection: object,
        *,
        definition: IndicatorDefinition,
        asset: str,
        measured_on: str,
        result: Result,
        **_: object,
    ) -> int:
        assert isinstance(connection, FakeConnection)
        persisted.append(
            {
                "indicator_key": definition.key,
                "asset": asset,
                "measured_on": measured_on,
                "status": result.status,
            }
        )
        return len(persisted)

    def record_ping(url: str, *, timeout: int) -> httpx.Response:
        pinged.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("HEALTHCHECKS_PING_URL", HEARTBEAT_URL)
    monkeypatch.setattr(heartbeat.psycopg, "connect", connect)
    monkeypatch.setattr(heartbeat.httpx, "get", record_ping)
    monkeypatch.setattr(
        pipeline, "_fetch_asset_active_addresses", _fetch_active_addresses
    )
    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)

    heartbeat.main_sol_active_addresses()

    assert connected_to == [DATABASE_URL]
    assert pinged == [HEARTBEAT_URL]
    assert persisted == [
        {
            "indicator_key": pipeline.SOL_ACTIVE_ADDRESSES_KEY,
            "asset": "SOL",
            "measured_on": "SOL",
            "status": "OK",
        }
    ]


@pytest.mark.integration
def test_live_scheduled_board_run_persists_registry_minus_sol_active_addresses(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    run = run_scheduled_board()
    row_ids = run_pipeline(postgres, fetcher=lambda: run)
    definitions = _scheduled_board_definitions()

    rows = postgres.execute(
        """
        select indicator_key, asset, measured_on, value, status, reason,
               source_vendor, endpoint, source_field, fetched_at, source_timestamp
        from datapoints
        where id = any(%s)
        """,
        (list(row_ids),),
    ).fetchall()

    assert len(_board_definitions()) == 84
    assert _expected_rows(definitions) == 87
    assert all(item.status == "AVAILABLE" for item in run.history.values())
    assert all(item.fetched_bars == 250 for item in run.history.values())

    ok_like = (
        Ok,
        FundingRateOk,
        OpenInterestOk,
        LongShortRatioOk,
        TakerRatioOk,
        FredOk,
        SosoValueEtfFlowOk,
        DefiLlamaStablecoinSupplyOk,
        AlternativeMeFearGreedOk,
        Stale,
    )
    for key, result in run.indicators.items():
        assert isinstance(result, (*ok_like, Unavailable, Error)), (
            f"{key} produced an untyped result: {result!r}"
        )
    # A live vendor may transiently fail without indicating a real defect (this test hits
    # real venues, not mocks) — the board's own job is to surface that per-cell, not crash.
    # A large fraction failing at once, however, is a real regression, not vendor noise.
    live_attempts = {
        key: result
        for key, result in run.indicators.items()
        if isinstance(result, (*ok_like, Error))
    }
    failures = {
        key: result for key, result in live_attempts.items() if isinstance(result, Error)
    }
    assert len(failures) / len(live_attempts) <= 0.1, (
        f"{len(failures)}/{len(live_attempts)} live indicators failed: {sorted(failures)}"
    )

    assert len(row_ids) == _expected_rows(definitions)
    assert len(rows) == _expected_rows(definitions)
    assert {row[0] for row in rows} == {definition.key for definition in definitions}
    assert pipeline.SOL_ACTIVE_ADDRESSES_KEY not in {row[0] for row in rows}
    assert sum(str(row[0]).endswith("_funding_rate") for row in rows) == 4
    assert sum(str(row[0]).endswith("_open_interest") for row in rows) == 4
    assert sum(str(row[0]).endswith("_long_short_ratio") for row in rows) == 4
    assert sum(str(row[0]).endswith("_taker_ratio") for row in rows) == 4
    assert sum(str(row[0]).endswith("_mvrv") for row in rows) == 3
    assert sum(str(row[0]).endswith("_active_addresses") for row in rows) == 3
    assert sum(str(row[0]).endswith("_exchange_flow") for row in rows) == 2
    assert sum(str(row[0]).endswith("_staking") for row in rows) == 1
    assert sum(str(row[0]).startswith("macro_") for row in rows) == 7
    assert sum(row[0] == "spot_etf_net_flow" for row in rows) == 3
    assert sum(row[0] == "stablecoin_supply" for row in rows) == 3
    assert sum(row[0] == "fear_greed_index" for row in rows) == 1
    assert all(row[1] == row[2] for row in rows)
    assert all(row[6] and row[7] and row[8] and row[9] for row in rows)
    for row in rows:
        value, status, reason, source_timestamp = row[3], row[4], row[5], row[10]
        if status in ("OK", "STALE"):
            assert value is not None and reason is None and source_timestamp is not None
        else:
            assert value is None and reason is not None and source_timestamp is None


@pytest.mark.integration
def test_live_sol_active_addresses_run_persists_that_cell_on_its_own(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    run = run_sol_active_addresses()
    row_ids = run_pipeline(postgres, fetcher=lambda: run)

    rows = postgres.execute(
        """
        select indicator_key, asset, measured_on, value, status, reason,
               source_vendor, endpoint, source_field, fetched_at, source_timestamp
        from datapoints
        where id = any(%s)
        """,
        (list(row_ids),),
    ).fetchall()

    assert len(row_ids) == 1
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == pipeline.SOL_ACTIVE_ADDRESSES_KEY
    assert row[1] == row[2] == "SOL"
    assert row[6] == "helius"
    assert row[7] and row[8] and row[9]
    value, status, reason, source_timestamp = row[3], row[4], row[5], row[10]
    if status in ("OK", "STALE"):
        assert value is not None and reason is None and source_timestamp is not None
    else:
        assert value is None and reason is not None and source_timestamp is None
