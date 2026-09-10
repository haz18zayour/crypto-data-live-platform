"""Fetch Coinbase's most recent closed BTC daily candle."""

from datetime import UTC, datetime, timedelta

import httpx

from ingest.schemas import CoinbaseCandleResponse
from ingest.status import Error, Ok, Reason, Result, Unavailable

ENDPOINT = (
    "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400"
)
MEASURED_ON = "BTC"
REQUEST_TIMEOUT_SECONDS = 10
DAILY_INTERVAL = timedelta(days=1)


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
