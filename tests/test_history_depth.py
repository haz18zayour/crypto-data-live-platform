from datetime import UTC, datetime, timedelta
from itertools import pairwise

import httpx
import pytest

from ingest.fetchers import coinbase, okx
from ingest.status import Error

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)
DAY = timedelta(days=1)


def okx_candle(opened_at: datetime) -> list[str]:
    value = str(opened_at.date().toordinal())
    return [
        str(int(opened_at.timestamp() * 1000)),
        value,
        value,
        value,
        value,
        value,
        value,
        value,
        "1",
    ]


def coinbase_candle(opened_at: datetime) -> list[int | float]:
    value = float(opened_at.date().toordinal())
    return [int(opened_at.timestamp()), value, value, value, value, value]


def okx_client(
    rows: list[list[str]],
    *,
    shorten_page: int | None = None,
) -> tuple[httpx.Client, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        limit = int(request.url.params["limit"])
        after = int(request.url.params["after"])
        start = next(
            (
                index + 1
                for index, row in enumerate(rows)
                if int(row[0]) == after
            ),
            0,
        )
        page = rows[start : start + limit]
        if shorten_page == len(requests):
            page = page[:-1]
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": page},
            request=request,
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def coinbase_client(
    rows: list[list[int | float]],
    *,
    shorten_page: int | None = None,
) -> tuple[httpx.Client, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        start = datetime.fromisoformat(request.url.params["start"])
        end = datetime.fromisoformat(request.url.params["end"])
        page = [
            row
            for row in rows
            if start <= datetime.fromtimestamp(row[0], tz=UTC) <= end
        ]
        if shorten_page == len(requests):
            page = page[:-1]
        return httpx.Response(200, json=page, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_a_request_needing_more_bars_than_one_page_returns_the_full_contiguous_series() -> (
    None
):
    opened = datetime(2026, 9, 9, tzinfo=UTC)
    okx_rows = [okx_candle(opened - index * DAY) for index in range(205)]
    coinbase_rows = [
        coinbase_candle(opened - index * DAY) for index in range(350)
    ]
    okx_http, okx_requests = okx_client(okx_rows)
    coinbase_http, coinbase_requests = coinbase_client(coinbase_rows)

    with okx_http, coinbase_http:
        okx_result = okx.fetch_btc_daily_bars(205, client=okx_http, now=NOW)
        coinbase_result = coinbase.fetch_btc_daily_bars(
            350, client=coinbase_http, now=NOW
        )

    assert not isinstance(okx_result, Error), okx_result
    assert [int(row[0]) for row in okx_result] == [int(row[0]) for row in okx_rows]
    assert [request.url.params["limit"] for request in okx_requests] == [
        "100",
        "100",
        "5",
    ]
    assert len({int(row[0]) for row in okx_result}) == 205

    assert not isinstance(coinbase_result, Error), coinbase_result
    assert [row.time for row in coinbase_result] == [
        int(row[0]) for row in coinbase_rows
    ]
    assert len(coinbase_requests) == 2
    assert len({row.time for row in coinbase_result}) == 350


def test_a_page_that_returns_fewer_rows_than_requested_fails_the_whole_fetch() -> (
    None
):
    opened = datetime(2026, 9, 9, tzinfo=UTC)
    okx_rows = [okx_candle(opened - index * DAY) for index in range(205)]
    coinbase_rows = [
        coinbase_candle(opened - index * DAY) for index in range(350)
    ]
    okx_http, okx_requests = okx_client(okx_rows, shorten_page=2)
    coinbase_http, coinbase_requests = coinbase_client(
        coinbase_rows, shorten_page=2
    )

    with okx_http, coinbase_http:
        okx_result = okx.fetch_btc_daily_bars(205, client=okx_http, now=NOW)
        coinbase_result = coinbase.fetch_btc_daily_bars(
            350, client=coinbase_http, now=NOW
        )

    assert isinstance(okx_result, Error)
    assert okx_result.detail == "OKX page returned 99 bars, expected 100"
    assert len(okx_requests) == 2
    assert isinstance(coinbase_result, Error)
    assert coinbase_result.detail == "Coinbase page returned 49 bars, expected 50"
    assert len(coinbase_requests) == 2


def test_a_gap_at_a_page_boundary_is_detected() -> None:
    opened = datetime(2026, 9, 9, tzinfo=UTC)
    okx_rows = [okx_candle(opened - index * DAY) for index in range(205)]
    okx_rows = okx_rows[:100] + okx_rows[101:] + [okx_candle(opened - 205 * DAY)]
    coinbase_rows = [
        coinbase_candle(opened - index * DAY) for index in range(350)
    ]
    coinbase_rows = (
        coinbase_rows[:300]
        + coinbase_rows[301:]
        + [coinbase_candle(opened - 350 * DAY)]
    )
    okx_http, _ = okx_client(okx_rows)
    coinbase_http, _ = coinbase_client(coinbase_rows)

    with okx_http, coinbase_http:
        okx_result = okx.fetch_btc_daily_bars(205, client=okx_http, now=NOW)
        coinbase_result = coinbase.fetch_btc_daily_bars(
            350, client=coinbase_http, now=NOW
        )

    assert isinstance(okx_result, Error)
    assert "not contiguous" in okx_result.detail
    assert isinstance(coinbase_result, Error)
    assert coinbase_result.detail == "Coinbase page returned 49 bars, expected 50"


def test_the_assembled_series_is_exactly_required_bars_long_newest_first() -> None:
    opened = datetime(2026, 9, 9, tzinfo=UTC)
    rows = [okx_candle(opened - index * DAY) for index in range(250)]
    client, _ = okx_client(rows)

    with client:
        result = okx.fetch_btc_daily_bars(250, client=client, now=NOW)

    assert not isinstance(result, Error), result
    assert len(result) == 250
    timestamps = [int(row[0]) for row in result]
    assert timestamps == sorted(timestamps, reverse=True)


def test_no_code_path_synthesises_or_pads_a_bar_to_reach_the_count() -> None:
    opened = datetime(2026, 9, 9, tzinfo=UTC)
    rows = [okx_candle(opened - index * DAY) for index in range(249)]
    original_rows = [row.copy() for row in rows]
    client, _ = okx_client(rows)

    with client:
        result = okx.fetch_btc_daily_bars(250, client=client, now=NOW)

    assert isinstance(result, Error)
    assert rows == original_rows
    assert len(rows) == 249


@pytest.mark.integration
def test_a_live_fetch_of_250_daily_bars_for_btc_succeeds_on_both_venues() -> None:
    okx_result = okx.fetch_btc_daily_bars(250)
    coinbase_result = coinbase.fetch_btc_daily_bars(250)

    assert not isinstance(okx_result, Error), okx_result
    assert not isinstance(coinbase_result, Error), coinbase_result
    assert len(okx_result) == len(coinbase_result) == 250

    okx_timestamps = [int(row[0]) for row in okx_result]
    coinbase_timestamps = [row.time for row in coinbase_result]
    assert all(
        newer - older == int(DAY.total_seconds() * 1000)
        for newer, older in pairwise(okx_timestamps)
    )
    assert all(
        newer - older == int(DAY.total_seconds())
        for newer, older in pairwise(coinbase_timestamps)
    )
