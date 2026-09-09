"""Fetch OKX's most recent final BTC daily close."""

from datetime import UTC, datetime, timedelta

import httpx

from ingest.registry import load_registry
from ingest.status import Error, Ok, Reason, Result, Unavailable

INDICATOR_KEY = "btc_daily_close"
MEASURED_ON = "BTC"
REQUEST_TIMEOUT_SECONDS = 10

ENDPOINT = next(
    entry.endpoint for entry in load_registry().root if entry.key == INDICATOR_KEY
)


def fetch_btc_daily_close(
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> Result:
    """Return the newest confirmed close, or an explicit failure result."""

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
            detail=f"OKX returned HTTP {error.response.status_code}",
        )
    except httpx.RequestError as error:
        return Error(reason=Reason.FETCH_FAILED, detail=f"OKX request failed: {error}")

    try:
        rows = response.json()["data"]
        closed = [row for row in rows if row[-1] == "1"]
        if not closed:
            return Unavailable(reason=Reason.FETCH_FAILED)

        newest = max(closed, key=lambda row: int(row[0]))
        source_timestamp = datetime.fromtimestamp(int(newest[0]) / 1000, tz=UTC)
        source_timestamp += timedelta(days=1)
        current_time = datetime.now(UTC) if now is None else now
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX source timestamp is in the future or present",
            )

        return Ok(value=float(newest[4]), source_timestamp=source_timestamp)
    except (IndexError, KeyError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX candle response: {error}",
        )
