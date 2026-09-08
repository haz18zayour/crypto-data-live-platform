from datetime import UTC, datetime, timedelta

import httpx
import pytest

from ingest.fetchers.okx import ENDPOINT, MEASURED_ON, fetch_btc_daily_close
from ingest.status import Error, Ok, Reason, Unavailable

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)
DAY_MILLISECONDS = 86_400_000


def milliseconds(value: datetime) -> str:
    return str(int(value.timestamp() * 1000))


def candle(opened_at: datetime, close: str, confirm: str) -> list[str]:
    return [milliseconds(opened_at), "1", "2", "0.5", close, "10", "10", "10", confirm]


def client_returning(
    rows: list[list[str]], status_code: int = 200
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_candles_with_confirm_not_equal_to_one_are_excluded() -> None:
    rows = [
        candle(NOW - timedelta(hours=12), "99", "0"),
        candle(NOW - timedelta(days=1, hours=1), "100", "2"),
        candle(NOW - timedelta(days=1, hours=12), "42.5", "1"),
        candle(NOW - timedelta(days=2, hours=12), "41", "1"),
    ]

    with client_returning(rows) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 42.5


def test_empty_result_after_filtering_returns_unavailable_fetch_failed() -> None:
    rows = [candle(NOW - timedelta(hours=12), "99", "0")]

    with client_returning(rows) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert result == Unavailable(reason=Reason.FETCH_FAILED)
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_http_error_returns_error_with_status_code_and_no_value() -> None:
    with client_returning([], status_code=503) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "503" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_source_timestamp_is_candle_close_time_and_must_be_in_the_past() -> None:
    opened_at = datetime(2026, 9, 7, tzinfo=UTC)
    with client_returning([candle(opened_at, "42.5", "1")]) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.source_timestamp == opened_at + timedelta(days=1)
    assert result.source_timestamp < NOW

    future_open = datetime(2026, 9, 8, tzinfo=UTC)
    with client_returning([candle(future_open, "43", "1")]) as client:
        future_result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()
    with pytest.raises(AttributeError):
        _ = future_result.value  # type: ignore[attr-defined]


def test_measured_on_equals_btc() -> None:
    assert MEASURED_ON == "BTC"


@pytest.mark.integration
def test_live_okx_request_returns_closed_btc_daily_candle() -> None:
    result = fetch_btc_daily_close()

    assert isinstance(result, Ok), result
    assert result.source_timestamp < datetime.now(UTC)

    response = httpx.get(ENDPOINT, timeout=10)
    response.raise_for_status()
    closed_rows = [row for row in response.json()["data"] if row[-1] == "1"]
    newest_closed = max(closed_rows, key=lambda row: int(row[0]))

    assert result.value == float(newest_closed[4])
    expected_close = datetime.fromtimestamp(
        (int(newest_closed[0]) + DAY_MILLISECONDS) / 1000,
        tz=UTC,
    )
    assert result.source_timestamp == expected_close
