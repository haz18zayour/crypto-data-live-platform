import os
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.sosovalue import (
    SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
    SosoValueEtfFlowOk,
    fetch_etf_net_flow,
)
from ingest.schemas import SosoValueEtfSummaryHistoryResponse
from ingest.status import Error, Reason


def sosovalue_payload(
    rows: list[dict[str, str]],
    *,
    code: int = 0,
    message: str = "success",
) -> dict[str, object]:
    return {"code": code, "message": message, "data": rows}


def summary_row(
    *,
    date: str = "2026-09-25",
    total_net_inflow: str = "-55066297.0000000000000000",
) -> dict[str, str]:
    return {
        "date": date,
        "total_net_inflow": total_net_inflow,
        "total_value_traded": "13534833596.0950000000000000",
        "total_net_assets": "152000000000.0000000000000000",
        "cum_net_inflow": "44000000000.0000000000000000",
    }


@pytest.mark.parametrize("symbol", ("BTC", "ETH", "SOL"))
def test_fetcher_authenticates_with_configured_sosovalue_header(symbol: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=sosovalue_payload([summary_row()]),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow(symbol, client=client, api_key="configured-token")

    assert isinstance(result, SosoValueEtfFlowOk)
    request = requests[0]
    assert request.headers["x-soso-api-key"] == "configured-token"
    assert request.url.params["symbol"] == symbol
    assert request.url.params["country_code"] == "US"


@pytest.mark.parametrize("symbol", ("BTC", "ETH", "SOL"))
def test_btc_eth_and_sol_return_real_decimal_net_flow_values(symbol: str) -> None:
    payload = sosovalue_payload(
        [
            summary_row(
                date="2026-09-25",
                total_net_inflow="-55066297.0000000000000000",
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow(symbol, client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.value == Decimal("-55066297.0000000000000000")
    assert not isinstance(result.value, float)
    assert result.source_timestamp == datetime(2026, 9, 25, tzinfo=UTC)
    assert result.reference_period == "2026-09-25"
    assert result.published_at == datetime(2026, 9, 25, tzinfo=UTC)


def test_long_decimal_money_round_trips_without_float_precision_loss() -> None:
    money = "12345678901234567890.1234567890123456"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=sosovalue_payload([summary_row(total_net_inflow=money)]),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("BTC", client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.value == Decimal(money)
    assert format(result.value, "f") == money


def test_reported_zero_persists_as_real_ok_zero_not_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=sosovalue_payload(
                [summary_row(total_net_inflow="0.0000000000000000")]
            ),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("ETH", client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.status == "OK"
    assert result.value == Decimal("0.0000000000000000")


def test_bnb_returns_not_definable_with_sosovalue_enum_reason() -> None:
    result = fetch_etf_net_flow("BNB", api_key="test-key")

    assert isinstance(result, Error)
    assert result.reason is Reason.NOT_DEFINABLE
    assert "SoSoValue" in result.detail
    assert "does not include BNB" in result.detail


def test_missing_sosovalue_api_key_fails_loudly_without_request() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=sosovalue_payload([summary_row()]))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("BTC", client=client, api_key="")

    assert requests == 0
    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "SOSOVALUE_API_KEY" in result.detail


def test_http_429_returns_fetch_failed_with_status_and_no_retry() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            json={"code": 42901, "message": "rate limit"},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("SOL", client=client, api_key="test-key")

    assert requests == 1
    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = sosovalue_payload([summary_row()])
    payload["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SosoValueEtfSummaryHistoryResponse.model_validate(payload)

    renamed = sosovalue_payload([summary_row()])
    row = renamed["data"][0]  # type: ignore[index]
    row["net_flow"] = row.pop("total_net_inflow")  # type: ignore[attr-defined]
    with pytest.raises(ValidationError, match="total_net_inflow"):
        SosoValueEtfSummaryHistoryResponse.model_validate(renamed)

    retyped = sosovalue_payload([summary_row()])
    retyped["data"][0]["total_net_inflow"] = 0.0  # type: ignore[index]
    with pytest.raises(ValidationError, match="string_type"):
        SosoValueEtfSummaryHistoryResponse.model_validate(retyped)


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = sosovalue_payload([summary_row()])
    payload["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("BTC", client=client, api_key="test-key")

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


@pytest.mark.integration
def test_live_sosovalue_request_returns_real_etf_flow_data_for_one_asset() -> None:
    if not os.environ.get("SOSOVALUE_API_KEY"):
        pytest.skip("SOSOVALUE_API_KEY is required for the live SoSoValue probe")

    result = fetch_etf_net_flow("BTC")

    assert isinstance(result, SosoValueEtfFlowOk), result
    assert result.value == result.value
    assert result.reference_period
