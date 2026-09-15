import math
from datetime import UTC, datetime, timedelta
from inspect import getsource

import httpx
import pytest
from pydantic import ValidationError

from ingest import pipeline
from ingest.fetchers.okx_derivatives import (
    BTC_FUNDING_RATE_HISTORY_ENDPOINT,
    BTC_USDT_SWAP_INST_ID,
    OKX_LONG_SHORT_RATIO_ENDPOINT,
    OKX_OPEN_INTEREST_ENDPOINT,
    OKX_TAKER_VOLUME_ENDPOINT,
    FundingRateOk,
    LongShortRatioOk,
    OpenInterestOk,
    TakerRatioOk,
    fetch_btc_funding_rate_history,
    fetch_long_short_ratio,
    fetch_open_interest,
    fetch_taker_ratio,
)
from ingest.pipeline import FetchedBars, Venue, run_all_assets
from ingest.schemas import (
    OkxFundingRateHistoryResponse,
    OkxLongShortRatioResponse,
    OkxOpenInterestResponse,
    OkxTakerVolumeResponse,
)
from ingest.status import Error, Ok, Reason, Result

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)


def milliseconds(value: datetime) -> str:
    return str(int(value.timestamp() * 1000))


def funding_row(
    settled_at: datetime,
    *,
    realized_rate: str = "0.000111",
    funding_rate: str = "0.999999",
) -> dict[str, str]:
    return {
        "formulaType": "withRate",
        "fundingRate": funding_rate,
        "fundingTime": milliseconds(settled_at),
        "instId": BTC_USDT_SWAP_INST_ID,
        "instType": "SWAP",
        "method": "current_period",
        "realizedRate": realized_rate,
    }


def synthetic_bars(asset: str, required_bars: int) -> FetchedBars:
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
    return FetchedBars(bars, NOW - timedelta(minutes=1))


def open_interest_row(
    asset: str,
    timestamp: datetime,
    *,
    oi_usd: str = "1350000000.12",
) -> dict[str, str]:
    return {
        "instId": f"{asset}-USDT-SWAP",
        "instType": "SWAP",
        "oi": "119718.23",
        "oiCcy": "11971.823",
        "oiUsd": oi_usd,
        "ts": milliseconds(timestamp),
    }


def long_short_ratio_row(timestamp: datetime, ratio: str = "1.38") -> list[str]:
    return [milliseconds(timestamp), ratio]


def taker_volume_row(
    timestamp: datetime, sell_volume: str = "100.0", buy_volume: str = "150.0"
) -> list[str]:
    return [milliseconds(timestamp), sell_volume, buy_volume]


def client_returning(
    rows: list[dict[str, str]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def open_interest_client_returning(
    rows: list[dict[str, str]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def long_short_ratio_client_returning(
    rows: list[list[str]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def taker_volume_client_returning(
    rows: list[list[str]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetcher_uses_history_endpoint_and_settled_realized_rate() -> None:
    rows = [
        funding_row(
            NOW - timedelta(hours=4),
            realized_rate="0.000123",
            funding_rate="0.999999",
        ),
        funding_row(NOW - timedelta(hours=8), realized_rate="0.000100"),
    ]
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, FundingRateOk)
    assert result.value == 0.000123
    assert requested_urls
    assert all("funding-rate-history" in url for url in requested_urls)
    assert all("public/funding-rate?" not in url for url in requested_urls)


def test_interval_is_derived_from_two_newest_funding_time_values() -> None:
    rows = [
        funding_row(NOW - timedelta(hours=2), realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=5), realized_rate="0.000100"),
    ]

    with client_returning(rows) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, FundingRateOk)
    assert "interval_seconds=10800" in result.source_field
    assert "fundingTime" in result.source_field

    source = getsource(fetch_btc_funding_rate_history)
    assert "28800" not in source


def test_source_field_records_runtime_interval_derivation() -> None:
    rows = [
        funding_row(NOW - timedelta(hours=1), realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=2), realized_rate="0.000100"),
    ]

    with client_returning(rows) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, FundingRateOk)
    assert result.source_field != "realizedRate"
    assert "realizedRate" in result.source_field
    assert "interval_seconds=3600" in result.source_field


def test_adversarial_funding_interval_change_uses_newest_gap_not_old_history() -> (
    None
):
    rows = [
        funding_row(NOW - timedelta(hours=1), realized_rate="0.000300"),
        funding_row(NOW - timedelta(hours=2), realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=10), realized_rate="0.000100"),
        funding_row(NOW - timedelta(hours=18), realized_rate="0.000090"),
        funding_row(NOW - timedelta(hours=26), realized_rate="0.000080"),
    ]

    with client_returning(rows) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, FundingRateOk)
    assert result.value == 0.000300
    assert result.source_timestamp == NOW - timedelta(hours=1)
    assert "interval_seconds=3600" in result.source_field
    assert "interval_seconds=28800" not in result.source_field
    assert "average" not in result.source_field.lower()


def test_two_assets_in_one_run_can_persist_different_derived_funding_intervals() -> (
    None
):
    funding_histories = {
        "BTC": [
            funding_row(NOW - timedelta(hours=1), realized_rate="0.000300"),
            funding_row(NOW - timedelta(hours=2), realized_rate="0.000200"),
            funding_row(NOW - timedelta(hours=10), realized_rate="0.000100"),
        ],
        "ETH": [
            funding_row(NOW - timedelta(hours=8), realized_rate="0.000030"),
            funding_row(NOW - timedelta(hours=16), realized_rate="0.000020"),
            funding_row(NOW - timedelta(hours=24), realized_rate="0.000010"),
        ],
    }

    def fetch_bars(venue: Venue, asset: str, required_bars: int) -> FetchedBars:
        return synthetic_bars(asset, required_bars)

    def fetch_funding_rate(asset: str) -> FundingRateOk:
        rows = funding_histories.get(
            asset,
            [
                funding_row(NOW - timedelta(hours=4), realized_rate="0.000040"),
                funding_row(NOW - timedelta(hours=8), realized_rate="0.000020"),
            ],
        )
        with client_returning(rows) as client:
            result = fetch_btc_funding_rate_history(client=client, now=NOW)
        assert isinstance(result, FundingRateOk)
        return result

    run = run_all_assets(
        fetch_bars=fetch_bars,
        fetch_funding_rate=fetch_funding_rate,
        fetch_open_interest=lambda asset: OpenInterestOk(
            value=1_000_000.0,
            source_timestamp=NOW - timedelta(minutes=1),
        ),
        fetch_long_short_ratio=lambda asset: LongShortRatioOk(
            value=1.1,
            source_timestamp=NOW - timedelta(minutes=1),
        ),
        fetch_taker_ratio=lambda asset: TakerRatioOk(
            value=1.2,
            source_timestamp=NOW - timedelta(minutes=1),
        ),
    )

    btc = run.indicators["btc_funding_rate"]
    eth = run.indicators["eth_funding_rate"]

    assert isinstance(btc, FundingRateOk)
    assert isinstance(eth, FundingRateOk)
    assert "interval_seconds=3600" in btc.source_field
    assert "interval_seconds=28800" in eth.source_field
    assert btc.source_field != eth.source_field


def test_persisted_funding_datapoint_source_field_names_derived_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        funding_row(NOW - timedelta(hours=1), realized_rate="0.000300"),
        funding_row(NOW - timedelta(hours=2), realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=10), realized_rate="0.000100"),
    ]
    with client_returning(rows) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)
    assert isinstance(result, FundingRateOk)

    persisted: dict[str, str] = {}

    def record_datapoint(
        connection: object,
        *,
        definition,
        asset: str,
        measured_on: str,
        result: Result,
    ) -> int:
        assert isinstance(result, Ok)
        persisted[definition.key] = definition.source_field
        return len(persisted)

    monkeypatch.setattr(pipeline, "persist_datapoint", record_datapoint)
    pipeline.persist_board(
        object(),  # type: ignore[arg-type]
        pipeline.FullAssetRun(indicators={"btc_funding_rate": result}, history={}),
    )

    assert persisted["btc_funding_rate"] == result.source_field
    assert "interval_seconds=3600" in persisted["btc_funding_rate"]
    assert "derived from the two newest consecutive fundingTime deltas" in persisted[
        "btc_funding_rate"
    ]


def test_fewer_than_two_settled_entries_is_fetch_failed_error() -> None:
    with client_returning([funding_row(NOW - timedelta(hours=4))]) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "fewer than two" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_http_error_returns_error_with_status_code_and_no_value() -> None:
    with client_returning([], status_code=429) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = {
        "code": "0",
        "msg": "",
        "data": [
            funding_row(NOW - timedelta(hours=4)),
            funding_row(NOW - timedelta(hours=8)),
        ],
    }
    payload["unexpected"] = "vendor reshape"  # type: ignore[index]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        OkxFundingRateHistoryResponse.model_validate(payload)

    renamed = funding_row(NOW - timedelta(hours=4))
    renamed["settlementTime"] = renamed.pop("fundingTime")
    with pytest.raises(ValidationError, match="fundingTime"):
        OkxFundingRateHistoryResponse.model_validate(
            {"code": "0", "msg": "", "data": [renamed]}
        )

    retyped = funding_row(NOW - timedelta(hours=4))
    retyped["realizedRate"] = None  # type: ignore[assignment]
    with pytest.raises(ValidationError, match="string_type"):
        OkxFundingRateHistoryResponse.model_validate(
            {"code": "0", "msg": "", "data": [retyped]}
        )


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = {
        "code": "0",
        "msg": "",
        "data": [
            funding_row(NOW - timedelta(hours=4)),
            funding_row(NOW - timedelta(hours=8)),
        ],
        "unexpected": "vendor reshape",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


def test_source_timestamp_is_newest_funding_time_and_must_be_past() -> None:
    newest = NOW - timedelta(hours=4)
    rows = [
        funding_row(newest, realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=8), realized_rate="0.000100"),
    ]

    with client_returning(rows) as client:
        result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(result, FundingRateOk)
    assert result.source_timestamp == newest
    assert result.source_timestamp < NOW

    future_rows = [
        funding_row(NOW, realized_rate="0.000200"),
        funding_row(NOW - timedelta(hours=4), realized_rate="0.000100"),
    ]
    with client_returning(future_rows) as client:
        future_result = fetch_btc_funding_rate_history(client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


def test_open_interest_requests_usdt_margined_swap_only() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "code": "0",
                "msg": "",
                "data": [open_interest_row("SOL", NOW - timedelta(minutes=1))],
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_open_interest("SOL", client=client, now=NOW)

    assert isinstance(result, OpenInterestOk)
    assert requested_urls == [
        f"{OKX_OPEN_INTEREST_ENDPOINT}?instType=SWAP&instId=SOL-USDT-SWAP"
    ]
    assert all("-USD-SWAP" not in url for url in requested_urls)


def test_open_interest_response_model_rejects_malformed_payload() -> None:
    payload = {
        "code": "0",
        "msg": "",
        "data": [open_interest_row("BTC", NOW - timedelta(minutes=1))],
        "unexpected": "vendor reshape",
    }

    with pytest.raises(ValidationError, match="extra_forbidden"):
        OkxOpenInterestResponse.model_validate(payload)

    renamed = open_interest_row("BTC", NOW - timedelta(minutes=1))
    renamed["timestamp"] = renamed.pop("ts")
    with pytest.raises(ValidationError, match="ts"):
        OkxOpenInterestResponse.model_validate(
            {"code": "0", "msg": "", "data": [renamed]}
        )


def test_open_interest_http_error_returns_error_with_status_code_and_no_value() -> (
    None
):
    with open_interest_client_returning([], status_code=429) as client:
        result = fetch_open_interest("BTC", client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_open_interest_source_timestamp_is_response_ts_and_must_be_past() -> None:
    timestamp = NOW - timedelta(minutes=1)
    with open_interest_client_returning(
        [open_interest_row("ETH", timestamp, oi_usd="123.45")]
    ) as client:
        result = fetch_open_interest("ETH", client=client, now=NOW)

    assert isinstance(result, OpenInterestOk)
    assert result.value == 123.45
    assert result.source_timestamp == timestamp
    assert result.source_timestamp < NOW

    with open_interest_client_returning([open_interest_row("ETH", NOW)]) as client:
        future_result = fetch_open_interest("ETH", client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


def test_long_short_ratio_requests_asset_currency_and_returns_newest_row() -> None:
    requested_urls: list[str] = []
    older = NOW - timedelta(minutes=10)
    newest = NOW - timedelta(minutes=5)
    rows = [
        long_short_ratio_row(older, "1.11"),
        long_short_ratio_row(newest, "1.42"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_long_short_ratio("SOL", client=client, now=NOW)

    assert isinstance(result, LongShortRatioOk)
    assert result.value == 1.42
    assert result.source_timestamp == newest
    assert requested_urls == [
        f"{OKX_LONG_SHORT_RATIO_ENDPOINT}?ccy=SOL&period=5m"
    ]


def test_long_short_ratio_response_model_rejects_malformed_payload() -> None:
    payload = {
        "code": "0",
        "msg": "",
        "data": [long_short_ratio_row(NOW - timedelta(minutes=5))],
        "unexpected": "vendor reshape",
    }

    with pytest.raises(ValidationError, match="extra_forbidden"):
        OkxLongShortRatioResponse.model_validate(payload)

    reshaped = [milliseconds(NOW - timedelta(minutes=5)), "1.38", "extra"]
    with pytest.raises(ValidationError):
        OkxLongShortRatioResponse.model_validate(
            {"code": "0", "msg": "", "data": [reshaped]}
        )


def test_long_short_ratio_http_error_returns_error_with_status_code_and_no_value() -> (
    None
):
    with long_short_ratio_client_returning([], status_code=429) as client:
        result = fetch_long_short_ratio("BTC", client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_long_short_ratio_source_timestamp_must_be_strictly_past() -> None:
    with long_short_ratio_client_returning(
        [long_short_ratio_row(NOW - timedelta(minutes=5), "1.23")]
    ) as client:
        result = fetch_long_short_ratio("ETH", client=client, now=NOW)

    assert isinstance(result, LongShortRatioOk)
    assert result.source_timestamp < NOW

    with long_short_ratio_client_returning([long_short_ratio_row(NOW)]) as client:
        future_result = fetch_long_short_ratio("ETH", client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


def test_taker_ratio_requests_asset_currency_and_returns_newest_row_ratio() -> None:
    requested_urls: list[str] = []
    older = NOW - timedelta(minutes=10)
    newest = NOW - timedelta(minutes=5)
    rows = [
        taker_volume_row(older, "100.0", "110.0"),
        taker_volume_row(newest, "100.0", "150.0"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_taker_ratio("SOL", client=client, now=NOW)

    assert isinstance(result, TakerRatioOk)
    assert result.value == 1.5
    assert result.source_timestamp == newest
    assert requested_urls == [
        f"{OKX_TAKER_VOLUME_ENDPOINT}?ccy=SOL&instType=CONTRACTS&period=5m"
    ]


def test_taker_ratio_response_model_rejects_malformed_payload() -> None:
    payload = {
        "code": "0",
        "msg": "",
        "data": [taker_volume_row(NOW - timedelta(minutes=5))],
        "unexpected": "vendor reshape",
    }

    with pytest.raises(ValidationError, match="extra_forbidden"):
        OkxTakerVolumeResponse.model_validate(payload)

    reshaped = [milliseconds(NOW - timedelta(minutes=5)), "100.0", "150.0", "extra"]
    with pytest.raises(ValidationError):
        OkxTakerVolumeResponse.model_validate(
            {"code": "0", "msg": "", "data": [reshaped]}
        )


def test_taker_ratio_http_error_returns_error_with_status_code_and_no_value() -> None:
    with taker_volume_client_returning([], status_code=429) as client:
        result = fetch_taker_ratio("BTC", client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_taker_ratio_source_timestamp_must_be_strictly_past() -> None:
    with taker_volume_client_returning(
        [taker_volume_row(NOW - timedelta(minutes=5), "100.0", "125.0")]
    ) as client:
        result = fetch_taker_ratio("ETH", client=client, now=NOW)

    assert isinstance(result, TakerRatioOk)
    assert result.source_timestamp < NOW

    with taker_volume_client_returning([taker_volume_row(NOW)]) as client:
        future_result = fetch_taker_ratio("ETH", client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


@pytest.mark.integration
def test_live_okx_request_returns_btc_settled_funding_history_with_derived_interval() -> (
    None
):
    result = fetch_btc_funding_rate_history()

    assert isinstance(result, FundingRateOk), result
    assert result.source_timestamp < datetime.now(UTC)

    response = httpx.get(
        BTC_FUNDING_RATE_HISTORY_ENDPOINT,
        params={"instId": BTC_USDT_SWAP_INST_ID, "limit": "2"},
        timeout=10,
    )
    response.raise_for_status()
    rows = OkxFundingRateHistoryResponse.model_validate(response.json()).data
    assert len(rows) >= 2

    newest = int(rows[0].funding_time)
    second_newest = int(rows[1].funding_time)
    interval_seconds = (newest - second_newest) // 1000

    assert result.value == float(rows[0].realized_rate)
    assert result.source_timestamp == datetime.fromtimestamp(newest / 1000, tz=UTC)
    assert f"interval_seconds={interval_seconds}" in result.source_field


@pytest.mark.integration
@pytest.mark.parametrize("asset", ("BTC", "ETH", "SOL", "BNB"))
def test_live_okx_request_returns_open_interest_for_usdt_margined_swap(
    asset: str,
) -> None:
    result = fetch_open_interest(asset)

    assert isinstance(result, OpenInterestOk), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0


@pytest.mark.integration
@pytest.mark.parametrize("asset", ("BTC", "ETH", "SOL", "BNB"))
def test_live_okx_request_returns_long_short_account_ratio_for_asset(
    asset: str,
) -> None:
    result = fetch_long_short_ratio(asset)

    assert isinstance(result, LongShortRatioOk), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0


@pytest.mark.integration
@pytest.mark.parametrize("asset", ("BTC", "ETH", "SOL", "BNB"))
def test_live_okx_request_returns_taker_buy_sell_ratio_for_asset(
    asset: str,
) -> None:
    result = fetch_taker_ratio(asset)

    assert isinstance(result, TakerRatioOk), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0
