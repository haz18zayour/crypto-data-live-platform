from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.coinmetrics import (
    COINMETRICS_ASSET_METRICS_ENDPOINT,
    CoinMetricsRateLimiter,
    _fetch_btc_metric,
    fetch_btc_mvrv,
)
from ingest.schemas import CoinMetricsAssetMetricsResponse
from ingest.status import Error, Ok, Reason, Unavailable

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)


def coinmetrics_payload(
    source_timestamp: datetime,
    *,
    value: str = "2.123456",
) -> dict[str, list[dict[str, str]]]:
    return {
        "data": [
            {
                "asset": "btc",
                "time": source_timestamp.isoformat().replace("+00:00", "Z"),
                "CapMVRVCur": value,
            }
        ]
    }


def test_fetcher_calls_asset_metrics_for_btc_mvrv_without_api_key() -> None:
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(
            200,
            json=coinmetrics_payload(NOW - timedelta(days=1)),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_mvrv(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert len(requested) == 1
    request = requested[0]
    assert str(request.url).startswith(COINMETRICS_ASSET_METRICS_ENDPOINT)
    assert request.url.params["assets"] == "btc"
    assert request.url.params["metrics"] == "CapMVRVCur"
    assert "api_key" not in request.url.params
    assert "apikey" not in request.url.params
    assert "authorization" not in {key.lower() for key in request.headers}
    assert "x-cm-api-key" not in {key.lower() for key in request.headers}


def test_bad_parameter_error_response_is_fetch_failed_with_message_and_no_value() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "bad_parameter",
                    "message": "Unsupported metric NotAMetric for btc",
                }
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _fetch_btc_metric("NotAMetric", client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "Unsupported metric NotAMetric for btc" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_forbidden_error_response_is_paywalled_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "type": "forbidden",
                    "message": "CapRealUSD requires credentials",
                }
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _fetch_btc_metric("CapRealUSD", client=client, now=NOW)

    assert isinstance(result, Unavailable)
    assert result.reason is Reason.PAYWALLED
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = coinmetrics_payload(NOW - timedelta(days=1))
    payload["unexpected"] = "vendor reshape"  # type: ignore[index]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        CoinMetricsAssetMetricsResponse.model_validate(payload)

    renamed = coinmetrics_payload(NOW - timedelta(days=1))
    renamed["data"][0]["CapMVRVCurrent"] = renamed["data"][0].pop("CapMVRVCur")
    with pytest.raises(ValidationError, match="CapMVRVCur"):
        CoinMetricsAssetMetricsResponse.model_validate(renamed)

    retyped = coinmetrics_payload(NOW - timedelta(days=1))
    retyped["data"][0]["CapMVRVCur"] = 2.123456  # type: ignore[assignment]
    with pytest.raises(ValidationError, match="string_type"):
        CoinMetricsAssetMetricsResponse.model_validate(retyped)


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = coinmetrics_payload(NOW - timedelta(days=1))
    payload["unexpected"] = "vendor reshape"  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_mvrv(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


def test_consecutive_requests_are_serialized_with_rate_limit_backoff() -> None:
    fake_time = 100.0
    request_times: list[float] = []

    def clock() -> float:
        return fake_time

    def sleeper(seconds: float) -> None:
        nonlocal fake_time
        fake_time += seconds

    def handler(request: httpx.Request) -> httpx.Response:
        request_times.append(fake_time)
        if len(request_times) > 1 and request_times[-1] - request_times[-2] < 0.625:
            return httpx.Response(429, request=request)
        return httpx.Response(
            200,
            json=coinmetrics_payload(NOW - timedelta(days=1)),
            request=request,
        )

    limiter = CoinMetricsRateLimiter(clock=clock, sleeper=sleeper)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = fetch_btc_mvrv(client=client, now=NOW, rate_limiter=limiter)
        second = fetch_btc_mvrv(client=client, now=NOW, rate_limiter=limiter)

    assert isinstance(first, Ok)
    assert isinstance(second, Ok)
    assert request_times == [100.0, 100.7]


def test_http_error_returns_error_with_status_code_and_no_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_mvrv(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "500" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_source_timestamp_is_response_time_and_must_be_strictly_past() -> None:
    source_timestamp = NOW - timedelta(days=1)

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=coinmetrics_payload(source_timestamp, value="2.5"),
                request=request,
            )
        )
    ) as client:
        result = fetch_btc_mvrv(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 2.5
    assert result.source_timestamp == source_timestamp
    assert result.source_timestamp < NOW

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=coinmetrics_payload(NOW),
                request=request,
            )
        )
    ) as client:
        future_result = fetch_btc_mvrv(client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


@pytest.mark.integration
def test_live_coinmetrics_request_returns_btc_current_mvrv() -> None:
    result = fetch_btc_mvrv()

    assert isinstance(result, Ok), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0


@pytest.mark.integration
def test_live_coinmetrics_caprealusd_is_paywalled_on_community_tier() -> None:
    result = _fetch_btc_metric("CapRealUSD")

    assert isinstance(result, Unavailable), result
    assert result.reason is Reason.PAYWALLED
