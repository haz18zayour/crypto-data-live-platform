from datetime import UTC, datetime, timedelta
from inspect import getsource

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.coinbase import (
    MEASURED_ON,
    fetch_btc_daily_close,
)
from ingest.registry import load_registry
from ingest.schemas import CoinbaseCandleResponse
from ingest.status import Error, Ok, Reason, Unavailable

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def seconds(value: datetime) -> int:
    return int(value.timestamp())


def candle(
    opened_at: datetime,
    *,
    low: float = 40.0,
    high: float = 50.0,
    open_: float = 41.0,
    close: float = 42.5,
    volume: float = 100.0,
) -> list[int | float]:
    return [seconds(opened_at), low, high, open_, close, volume]


def client_returning(
    rows: list[list[int | float]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=rows, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetcher_reads_close_by_its_named_field_not_a_shared_array_index() -> None:
    opened_at = datetime(2026, 9, 8, tzinfo=UTC)
    with client_returning(
        [candle(opened_at, low=1.0, high=2.0, open_=3.0, close=4.0)]
    ) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 4.0
    source = getsource(fetch_btc_daily_close)
    assert "newest.close" in source
    assert "newest[4]" not in source

    definition = next(
        entry for entry in load_registry().root if entry.key == "btc_daily_close"
    )
    assert "coinbase.close" in definition.source_field


def test_daily_source_timestamp_falls_on_a_utc_midnight_boundary() -> None:
    aligned = datetime(2026, 9, 8, tzinfo=UTC)
    with client_returning([candle(aligned)]) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.source_timestamp.tzinfo is UTC
    assert (
        result.source_timestamp.hour,
        result.source_timestamp.minute,
        result.source_timestamp.second,
    ) == (0, 0, 0)

    misaligned = aligned + timedelta(hours=1)
    with client_returning([candle(misaligned)]) as client:
        misaligned_result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(misaligned_result, Error)
    assert misaligned_result.reason is Reason.FETCH_FAILED
    assert "UTC midnight" in misaligned_result.detail


def valid_payload() -> list[list[int | float]]:
    return [candle(datetime(2026, 9, 8, tzinfo=UTC))]


def test_response_model_rejects_an_added_field() -> None:
    payload = valid_payload()
    payload[0].append(999.0)

    with pytest.raises(ValidationError):
        CoinbaseCandleResponse.model_validate(payload)

    named_payload = {
        "time": seconds(datetime(2026, 9, 8, tzinfo=UTC)),
        "low": 40.0,
        "high": 50.0,
        "open": 41.0,
        "close": 42.5,
        "volume": 100.0,
        "unexpected": 999.0,
    }
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CoinbaseCandleResponse.model_validate([named_payload])


def test_response_model_rejects_a_renamed_field() -> None:
    payload = {
        "time": seconds(datetime(2026, 9, 8, tzinfo=UTC)),
        "low": 40.0,
        "high": 50.0,
        "open": 41.0,
        "closing": 42.5,
        "volume": 100.0,
    }

    with pytest.raises(ValidationError):
        CoinbaseCandleResponse.model_validate([payload])


def test_response_model_rejects_a_type_change() -> None:
    payload: list[object] = [
        seconds(datetime(2026, 9, 8, tzinfo=UTC)),
        40.0,
        50.0,
        41.0,
        "42.5",
        100.0,
    ]

    with pytest.raises(ValidationError):
        CoinbaseCandleResponse.model_validate([payload])


def test_fetch_failure_returns_error_with_fetch_failed_never_ok() -> None:
    with client_returning([], status_code=503) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Error)
    assert not isinstance(result, Ok)
    assert result.reason is Reason.FETCH_FAILED
    assert "503" in result.detail


def test_bucket_convention_matches_okx_stored_bucket_end() -> None:
    bucket_start = datetime(2026, 9, 8, tzinfo=UTC)
    with client_returning([candle(bucket_start)]) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.source_timestamp == bucket_start + timedelta(days=1)


def test_current_coinbase_bucket_is_not_returned_as_closed() -> None:
    current_bucket = datetime(2026, 9, 9, tzinfo=UTC)
    newest_closed_bucket = datetime(2026, 9, 8, tzinfo=UTC)
    with client_returning(
        [
            candle(current_bucket, close=99.0),
            candle(newest_closed_bucket, close=42.5),
        ]
    ) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 42.5
    assert result.source_timestamp == current_bucket


def test_no_closed_bucket_returns_unavailable_not_a_fabricated_value() -> None:
    current_bucket = datetime(2026, 9, 9, tzinfo=UTC)
    with client_returning([candle(current_bucket)]) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert result == Unavailable(reason=Reason.FETCH_FAILED)


def test_measured_on_equals_btc() -> None:
    assert MEASURED_ON == "BTC"


@pytest.mark.integration
def test_live_coinbase_request_returns_closed_btc_daily_candle_on_utc_boundary() -> (
    None
):
    result = fetch_btc_daily_close()

    assert isinstance(result, Ok), result
    assert result.source_timestamp < datetime.now(UTC)
    assert (
        result.source_timestamp.hour,
        result.source_timestamp.minute,
        result.source_timestamp.second,
    ) == (0, 0, 0)
