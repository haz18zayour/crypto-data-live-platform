"""Fetch Coinbase's most recent closed BTC daily candle."""

from datetime import UTC, datetime, timedelta
from itertools import pairwise

import httpx

from ingest.schemas import CoinbaseCandle, CoinbaseCandleResponse
from ingest.status import Error, Ok, Reason, Result, Unavailable

ENDPOINT = (
    "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400"
)
MEASURED_ON = "BTC"
REQUEST_TIMEOUT_SECONDS = 10
DAILY_INTERVAL = timedelta(days=1)
HISTORY_ENDPOINT = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
HISTORY_PAGE_LIMIT = 300


def fetch_btc_daily_bars(
    required_bars: int,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple[CoinbaseCandle, ...] | Error:
    """Return exactly ``required_bars`` closed BTC candles, newest first."""

    current_time = datetime.now(UTC) if now is None else now
    upper_bound = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if upper_bound == current_time:
        upper_bound -= DAILY_INTERVAL
    rows: list[CoinbaseCandle] = []

    while len(rows) < required_bars:
        page_size = min(HISTORY_PAGE_LIMIT, required_bars - len(rows))
        lower_bound = upper_bound - page_size * DAILY_INTERVAL
        params = {
            "granularity": "86400",
            "start": lower_bound.isoformat(),
            "end": (upper_bound - timedelta(microseconds=1)).isoformat(),
        }
        try:
            response = (
                httpx.get(
                    HISTORY_ENDPOINT,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if client is None
                else client.get(
                    HISTORY_ENDPOINT,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Coinbase returned HTTP {error.response.status_code}",
            )
        except httpx.RequestError as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Coinbase request failed: {error}",
            )

        try:
            page = CoinbaseCandleResponse.model_validate(response.json()).root
            if len(page) < page_size:
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail=(
                        f"Coinbase page returned {len(page)} bars, "
                        f"expected {page_size}"
                    ),
                )
            selected = tuple(
                row
                for row in page
                if lower_bound
                <= datetime.fromtimestamp(row.time, tz=UTC)
                < upper_bound
            )
            if len(selected) != page_size:
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail=(
                        f"Coinbase page returned {len(selected)} bars, "
                        f"expected {page_size}"
                    ),
                )
            rows.extend(selected)
            upper_bound = lower_bound
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Invalid Coinbase candle response: {error}",
            )

    timestamps = [row.time for row in rows]
    interval_seconds = int(DAILY_INTERVAL.total_seconds())
    if any(newer <= older for newer, older in pairwise(timestamps)):
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="Coinbase candle timestamps are not strictly ordered newest-first",
        )
    if any(
        newer - older != interval_seconds
        for newer, older in pairwise(timestamps)
    ):
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=(
                "Coinbase candle timestamps are not contiguous at the expected "
                f"{interval_seconds}-second interval"
            ),
        )
    if any(
        datetime.fromtimestamp(timestamp, tz=UTC).time() != datetime.min.time()
        for timestamp in timestamps
    ):
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="Coinbase daily bucket is not aligned to UTC midnight",
        )
    if len(rows) != required_bars:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Coinbase returned {len(rows)} bars, expected {required_bars}",
        )
    return tuple(rows)


def fetch_btc_daily_close(
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> Result:
    """Return Coinbase's newest completed UTC-day close."""

    try:
        response = (
            httpx.get(ENDPOINT, timeout=REQUEST_TIMEOUT_SECONDS)
            if client is None
            else client.get(ENDPOINT, timeout=REQUEST_TIMEOUT_SECONDS)
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Coinbase returned HTTP {error.response.status_code}",
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Coinbase request failed: {error}",
        )

    try:
        rows = CoinbaseCandleResponse.model_validate(response.json()).root
        bucket_ends = []
        for row in rows:
            bucket_start = datetime.fromtimestamp(row.time, tz=UTC)
            if (
                bucket_start.hour,
                bucket_start.minute,
                bucket_start.second,
            ) != (0, 0, 0):
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail=(
                        "Coinbase daily bucket is not aligned to UTC midnight: "
                        f"{bucket_start.isoformat()}"
                    ),
                )
            bucket_ends.append((row, bucket_start + DAILY_INTERVAL))

        current_time = datetime.now(UTC) if now is None else now
        closed = [item for item in bucket_ends if item[1] < current_time]
        if not closed:
            return Unavailable(reason=Reason.FETCH_FAILED)

        newest, source_timestamp = max(closed, key=lambda item: item[1])
        return Ok(value=newest.close, source_timestamp=source_timestamp)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid Coinbase candle response: {error}",
        )
