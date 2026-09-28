from datetime import UTC, datetime
from decimal import Decimal

import httpx

from ingest.backfill import BACKFILL_RECIPES
from ingest.fetchers.defillama_stablecoins import (
    DEFILLAMA_STABLECOINCHAINS_ENDPOINT,
    DefiLlamaStablecoinSupplyOk,
    backfill_defillama_stablecoin_supply,
    fetch_stablecoin_supply,
)
from ingest.registry import load_registry
from ingest.status import Error, Reason


def _chart_row(timestamp: int, value: float) -> dict[str, object]:
    return {"date": str(timestamp), "totalCirculatingUSD": {"peggedUSD": value}}


def _current_payload() -> list[dict[str, object]]:
    return [
        {"name": "Ethereum", "totalCirculatingUSD": {"peggedUSD": 146.0}},
        {"name": "Solana", "totalCirculatingUSD": {"peggedUSD": 16.0}},
        {"name": "BSC", "totalCirculatingUSD": {"peggedUSD": 13.0}},
    ]


def test_defillama_registry_entry_is_wired_to_real_backfill_recipe() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")

    assert entry.backfill_recipe == "defillama_stablecoincharts"
    assert BACKFILL_RECIPES[entry.backfill_recipe] is backfill_defillama_stablecoin_supply


def test_defillama_backfill_reads_stablecoincharts_for_eth_solana_and_bsc() -> None:
    requested_paths: list[str] = []
    newest = int(datetime(2026, 9, 28, tzinfo=UTC).timestamp())
    older = int(datetime(2026, 9, 27, tzinfo=UTC).timestamp())

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        chain = request.url.path.rsplit("/", 1)[-1]
        values = {"Ethereum": 146.0, "Solana": 16.0, "BSC": 13.0}
        return httpx.Response(
            200,
            json=[_chart_row(older, values[chain] - 1.0), _chart_row(newest, values[chain])],
            request=request,
        )

    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_defillama_stablecoin_supply(entry, client=client)

    assert requested_paths == [
        "/stablecoincharts/Ethereum",
        "/stablecoincharts/Solana",
        "/stablecoincharts/BSC",
    ]
    newest_values = {
        next(iter(run.indicators.keys())).split("\x1f")[1]: next(
            iter(run.indicators.values())
        )
        for run in runs
        if next(iter(run.indicators.values())).source_timestamp
        == datetime(2026, 9, 28, tzinfo=UTC)
    }
    assert len(newest_values) == 3
    assert all(isinstance(value, DefiLlamaStablecoinSupplyOk) for value in newest_values.values())
    assert newest_values["ETH"].value == Decimal("146.0")
    assert newest_values["SOL"].value == Decimal("16.0")
    assert newest_values["BNB"].value == Decimal("13.0")


def test_defillama_latest_backfill_matches_current_live_endpoint_same_day() -> None:
    newest = int(datetime(2026, 9, 28, tzinfo=UTC).timestamp())

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DEFILLAMA_STABLECOINCHAINS_ENDPOINT:
            return httpx.Response(200, json=_current_payload(), request=request)
        chain = request.url.path.rsplit("/", 1)[-1]
        values = {"Ethereum": 146.0, "Solana": 16.0, "BSC": 13.0}
        return httpx.Response(
            200,
            json=[_chart_row(newest, values[chain])],
            request=request,
        )

    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_defillama_stablecoin_supply(entry, client=client)
        live = {
            asset: fetch_stablecoin_supply(asset, client=client, now=datetime(2026, 9, 28, 12, tzinfo=UTC))
            for asset in ("ETH", "SOL", "BNB")
        }

    latest = {
        next(iter(run.indicators.keys())).split("\x1f")[1]: next(iter(run.indicators.values()))
        for run in runs
    }
    for asset, live_value in live.items():
        assert isinstance(live_value, DefiLlamaStablecoinSupplyOk)
        backfilled = latest[asset]
        assert isinstance(backfilled, DefiLlamaStablecoinSupplyOk)
        assert backfilled.reference_period == "2026-09-28"
        assert backfilled.value == live_value.value


def test_btc_stablecoin_supply_remains_not_definable_and_not_backfilled() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            json=[_chart_row(int(datetime(2026, 9, 28, tzinfo=UTC).timestamp()), 1.0)],
            request=request,
        )

    entry = next(entry for entry in load_registry().root if entry.key == "stablecoin_supply")
    assert entry.not_definable is not None
    assert entry.not_definable.reason_for("BTC")
    assert "BTC" not in entry.definable_for
    assert isinstance(fetch_stablecoin_supply("BTC"), Error)
    assert fetch_stablecoin_supply("BTC").reason is Reason.NOT_DEFINABLE

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backfill_defillama_stablecoin_supply(entry, client=client)

    assert not any(path.endswith("/Bitcoin") for path in requested_paths)
