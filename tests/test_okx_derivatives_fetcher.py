from datetime import UTC, datetime, timedelta
from inspect import getsource

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.okx_derivatives import (
    BTC_FUNDING_RATE_HISTORY_ENDPOINT,
    BTC_USDT_SWAP_INST_ID,
    FundingRateOk,
    fetch_btc_funding_rate_history,
)
from ingest.schemas import OkxFundingRateHistoryResponse
from ingest.status import Error, Reason

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
