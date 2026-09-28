import os
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.sosovalue import (
    SosoValueEtfFlowOk,
    fetch_etf_net_flow,
)
from ingest.schemas import SosoValueEtfSummaryHistoryResponse
from ingest.status import Error, Reason


def sosovalue_payload(
    rows: list[dict[str, object]],
    *,
    code: int = 0,
    message: str = "success",
) -> dict[str, object]:
    return {"code": code, "message": message, "data": rows}


def summary_row(
    *,
    date: str = "2026-09-25",
    total_net_inflow: float = -55066297.155,
) -> dict[str, object]:
    # Confirmed live, 2026-09-28: SoSoValue returns these as JSON floats, not the
    # long-decimal strings originally assumed from research/docs examples.
    return {
        "date": date,
        "total_net_inflow": total_net_inflow,
        "total_value_traded": 13534833596.095,
        "total_net_assets": 152000000000.0,
        "cum_net_inflow": 44000000000.0,
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


def test_fetcher_reads_sosovalue_token_from_environment_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=sosovalue_payload([summary_row()]),
            request=request,
        )

    monkeypatch.setenv("SOSOVALUE_API_KEY", "env-token")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("BTC", client=client)

    assert isinstance(result, SosoValueEtfFlowOk)
    assert requests[0].headers["x-soso-api-key"] == "env-token"


@pytest.mark.parametrize("symbol", ("BTC", "ETH", "SOL"))
def test_btc_eth_and_sol_return_real_decimal_net_flow_values(symbol: str) -> None:
    payload = sosovalue_payload(
        [
            summary_row(
                date="2026-09-25",
                total_net_inflow=-55066297.155,
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow(symbol, client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.value == Decimal("-55066297.155")
    assert not isinstance(result.value, float)
    assert result.source_timestamp == datetime(2026, 9, 25, tzinfo=UTC)
    assert result.reference_period == "2026-09-25"
    assert result.published_at == datetime(2026, 9, 25, tzinfo=UTC)


def test_money_round_trips_via_str_conversion_without_binary_float_noise() -> None:
    # Decimal(str(value)) must be used, never Decimal(value) directly on a float - the
    # latter preserves the float's own binary imprecision. 0.1 is the canonical example:
    # Decimal(0.1) != Decimal("0.1") because 0.1 has no exact binary representation.
    money = 190646110.255

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=sosovalue_payload([summary_row(total_net_inflow=money)]),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("BTC", client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.value == Decimal("190646110.255")
    assert result.value != Decimal(money)  # proves str() conversion is load-bearing


def test_reported_zero_persists_as_real_ok_zero_not_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=sosovalue_payload([summary_row(total_net_inflow=0.0)]),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_etf_net_flow("ETH", client=client, api_key="test-key")

    assert isinstance(result, SosoValueEtfFlowOk)
    assert result.status == "OK"
    assert result.value == Decimal(0)


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
    retyped["data"][0]["total_net_inflow"] = "not-a-number"  # type: ignore[index]
    with pytest.raises(ValidationError, match="float_type"):
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
    assert isinstance(result.value, Decimal)
    assert result.reference_period
    # A real trading-day date string (YYYY-MM-DD), not an empty/placeholder value.
    assert len(result.reference_period) == 10
    assert result.reference_period[4] == "-" and result.reference_period[7] == "-"
    assert result.published_at.tzinfo is not None
    assert result.published_at <= datetime.now(UTC)
