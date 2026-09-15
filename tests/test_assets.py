from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from ingest import pipeline
from ingest.fetchers.okx_derivatives import (
    FundingRateOk,
    LongShortRatioOk,
    OpenInterestOk,
    TakerRatioOk,
)
from ingest.pipeline import (
    FetchedBars,
    FundingRateResult,
    HistoryAvailability,
    LongShortRatioResult,
    OpenInterestResult,
    TakerRatioResult,
    Venue,
    assess_history,
    load_history_availability,
    run_all_assets,
)
from ingest.registry import load_registry
from ingest.status import Ok

ASSETS = {"BTC", "ETH", "SOL", "BNB"}
VENUES = {"okx", "coinbase"}
MEASUREMENT_DATE = date(2026, 9, 10)
SOURCE_TIMESTAMP = datetime(2026, 9, 10, tzinfo=UTC)


def synthetic_bars(asset: str, required_bars: int) -> FetchedBars:
    offset = {"BTC": 40_000.0, "ETH": 2_000.0, "SOL": 100.0, "BNB": 500.0}[
        asset
    ]
    bars = []
    for index in range(required_bars):
        close = offset + index * 0.2 + math.sin(index / 3) * 5
        bars.append(
            {
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1_000.0 + index,
            }
        )
    return FetchedBars(tuple(bars), SOURCE_TIMESTAMP)


def synthetic_funding_rate(asset: str) -> FundingRateResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return FundingRateOk(
        value=offset / 100_000,
        source_timestamp=SOURCE_TIMESTAMP,
        source_field=(
            "OKX funding-rate-history realizedRate; interval_seconds=28800 "
            "derived from the two newest consecutive fundingTime deltas"
        ),
    )


def synthetic_open_interest(asset: str) -> OpenInterestResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return OpenInterestOk(
        value=offset * 1_000_000,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def synthetic_long_short_ratio(asset: str) -> LongShortRatioResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return LongShortRatioOk(
        value=1.0 + offset / 10,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def synthetic_taker_ratio(asset: str) -> TakerRatioResult:
    offset = {"BTC": 1.0, "ETH": 2.0, "SOL": 3.0, "BNB": 4.0}[asset]
    return TakerRatioOk(
        value=1.0 + offset / 10,
        source_timestamp=SOURCE_TIMESTAMP,
    )


def test_registry_declares_measured_history_availability_per_asset_per_venue() -> (
    None
):
    availability = load_history_availability()

    assert {(item.asset, item.venue) for item in availability} == {
        (asset, venue) for asset in ASSETS for venue in VENUES
    }
    for item in availability:
        assert isinstance(item.available_bars, int)
        assert item.available_bars > 0
        assert item.measured_on == MEASUREMENT_DATE


def test_asset_with_fewer_available_bars_than_required_is_declared_uncorroborated_at_venue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = list(load_history_availability())
    short = HistoryAvailability(
        asset="BNB",
        venue="coinbase",
        available_bars=249,
        measured_on=MEASUREMENT_DATE,
        exact=True,
    )
    bnb_coinbase = next(
        item
        for item in declared
        if (item.asset, item.venue) == ("BNB", "coinbase")
    )
    declared[declared.index(bnb_coinbase)] = short
    monkeypatch.setattr(
        "ingest.pipeline.load_history_availability", lambda: tuple(declared)
    )
    calls: list[tuple[str, str, int]] = []

    def fetch_bars(
        venue: Venue, asset: str, required_bars: int
    ) -> FetchedBars:
        calls.append((venue, asset, required_bars))
        return synthetic_bars(asset, required_bars)

    run = run_all_assets(
        fetch_bars=fetch_bars,
        fetch_funding_rate=synthetic_funding_rate,
        fetch_open_interest=synthetic_open_interest,
        fetch_long_short_ratio=synthetic_long_short_ratio,
        fetch_taker_ratio=synthetic_taker_ratio,
    )
    assessment = run.history[("BNB", "coinbase")]

    assert assessment.status == "UNCORROBORATED"
    assert assessment.reason == (
        "coinbase has 249 measured daily bars for BNB, fewer than the 250 required"
    )
    assert ("coinbase", "BNB", 250) not in calls
    assert all(
        isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
        for key, result in run.indicators.items()
        if key.startswith("bnb_")
    )


def test_bnb_coinbase_availability_is_recorded_and_compared_against_required_bars() -> (
    None
):
    availability = next(
        item
        for item in load_history_availability()
        if (item.asset, item.venue) == ("BNB", "coinbase")
    )
    bnb_required_bars = max(
        definition.required_bars or 0
        for definition in load_registry().root
        if definition.definable_for == ("BNB",)
    )
    assessment = assess_history(availability, bnb_required_bars)

    assert availability.available_bars == 317
    assert availability.measured_on == MEASUREMENT_DATE
    assert availability.exact is True
    assert bnb_required_bars == 250
    assert assessment.status == "AVAILABLE"
    assert assessment.surplus_bars == 67
    assert assess_history(availability, 318).status == "UNCORROBORATED"


def test_all_four_assets_produce_an_indicator_value_or_explicit_status() -> None:
    calls: list[tuple[str, str, int]] = []

    def fetch_bars(
        venue: Venue, asset: str, required_bars: int
    ) -> FetchedBars:
        calls.append((venue, asset, required_bars))
        return synthetic_bars(asset, required_bars)

    run = run_all_assets(
        fetch_bars=fetch_bars,
        fetch_funding_rate=synthetic_funding_rate,
        fetch_open_interest=synthetic_open_interest,
        fetch_long_short_ratio=synthetic_long_short_ratio,
        fetch_taker_ratio=synthetic_taker_ratio,
    )
    technical_definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_candle"
    )
    funding_definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_funding_rate_history"
    )
    open_interest_definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_open_interest"
    )
    long_short_definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_long_short_ratio"
    )
    taker_ratio_definitions = tuple(
        definition
        for definition in load_registry().root
        if definition.response_model == "okx_taker_volume"
    )

    assert set(run.indicators) == {
        definition.key
        for definition in (
            *technical_definitions,
            *funding_definitions,
            *open_interest_definitions,
            *long_short_definitions,
            *taker_ratio_definitions,
        )
    }
    assert Counter(
        definition.definable_for[0] for definition in technical_definitions
    ) == Counter({"BTC": 12, "ETH": 11, "SOL": 11, "BNB": 11})
    assert Counter(
        definition.definable_for[0] for definition in funding_definitions
    ) == Counter({asset: 1 for asset in ASSETS})
    assert Counter(
        definition.definable_for[0] for definition in open_interest_definitions
    ) == Counter({asset: 1 for asset in ASSETS})
    assert Counter(
        definition.definable_for[0] for definition in long_short_definitions
    ) == Counter({asset: 1 for asset in ASSETS})
    assert Counter(
        definition.definable_for[0] for definition in taker_ratio_definitions
    ) == Counter({asset: 1 for asset in ASSETS})
    assert all(
        result.status in {"OK", "STALE", "UNAVAILABLE", "ERROR"}
        for result in run.indicators.values()
    )
    assert all(
        isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
        for result in run.indicators.values()
    )
    assert all(
        math.isfinite(result.value)
        for result in run.indicators.values()
        if isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
    )
    assert set(calls) == {
        (venue, asset, 250) for asset in ASSETS for venue in VENUES
    }


def test_full_run_routes_each_asset_to_its_actual_pair_at_both_venues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_pairs: set[tuple[str, str]] = set()

    def close_for(opened_at: datetime) -> float:
        ordinal = opened_at.date().toordinal()
        return 100.0 + ordinal * 0.2 + math.sin(ordinal / 3) * 5

    def fake_get(
        url: str,
        *,
        params: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        assert timeout == 10
        request = httpx.Request("GET", url, params=params)
        if "okx.com" in url:
            pair = params["instId"]
            requested_pairs.add(("okx", pair))
            after = datetime.fromtimestamp(int(params["after"]) / 1000, tz=UTC)
            okx_rows = []
            for offset in range(1, int(params["limit"]) + 1):
                opened_at = after - timedelta(days=offset)
                close = close_for(opened_at)
                okx_rows.append(
                    [
                        str(int(opened_at.timestamp() * 1000)),
                        str(close),
                        str(close + 2),
                        str(close - 2),
                        str(close),
                        str(1_000 + offset),
                        "0",
                        "0",
                        "1",
                    ]
                )
            return httpx.Response(
                200,
                json={"code": "0", "msg": "", "data": okx_rows},
                request=request,
            )

        pair = url.split("/products/", 1)[1].split("/", 1)[0]
        requested_pairs.add(("coinbase", pair))
        start = datetime.fromisoformat(params["start"])
        end = datetime.fromisoformat(params["end"])
        days = (end.date() - start.date()).days + 1
        coinbase_rows = []
        for offset in reversed(range(days)):
            opened_at = start + timedelta(days=offset)
            close = close_for(opened_at)
            coinbase_rows.append(
                [
                    int(opened_at.timestamp()),
                    close - 2,
                    close + 2,
                    close,
                    close,
                    1_000.0 + offset,
                ]
            )
        return httpx.Response(200, json=coinbase_rows, request=request)

    monkeypatch.setattr(pipeline.httpx, "get", fake_get)

    run = run_all_assets(
        fetch_funding_rate=synthetic_funding_rate,
        fetch_open_interest=synthetic_open_interest,
        fetch_long_short_ratio=synthetic_long_short_ratio,
        fetch_taker_ratio=synthetic_taker_ratio,
    )

    assert requested_pairs == {
        *(("okx", f"{asset}-USDT") for asset in ASSETS),
        *(("coinbase", f"{asset}-USD") for asset in ASSETS),
    }
    assert all(item.status == "AVAILABLE" for item in run.history.values())
    assert all(
        isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
        for result in run.indicators.values()
    )


@pytest.mark.integration
def test_full_run_computes_indicators_for_btc_eth_sol_bnb_against_live_venues() -> (
    None
):
    run = run_all_assets()

    assert {asset for asset, _ in run.history} == ASSETS
    assert {venue for _, venue in run.history} == VENUES
    assert all(item.status == "AVAILABLE" for item in run.history.values())
    assert all(item.fetched_bars == 250 for item in run.history.values())
    assert all(
        isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
        for result in run.indicators.values()
    )
    assert all(
        math.isfinite(result.value)
        for result in run.indicators.values()
        if isinstance(
            result,
            (Ok, FundingRateOk, OpenInterestOk, LongShortRatioOk, TakerRatioOk),
        )
    )
