"""Fetch OKX settled derivatives metrics."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from typing import Literal

import httpx

from ingest.schemas import OkxFundingRateHistoryResponse
from ingest.status import Error, Reason

BTC_FUNDING_RATE_HISTORY_ENDPOINT = (
    "https://www.okx.com/api/v5/public/funding-rate-history"
)
BTC_USDT_SWAP_INST_ID = "BTC-USDT-SWAP"
REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class FundingRateOk:
    """A settled funding rate plus the source-field derivation used for it."""

    value: float
    source_timestamp: datetime
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_timestamp, datetime):
            raise TypeError("source_timestamp must be a datetime")
        if not self.source_field.strip():
            raise ValueError("source_field must be non-empty")


type FundingRateResult = FundingRateOk | Error


def _interval_source_field(interval_seconds: int) -> str:
    return (
        "OKX funding-rate-history realizedRate; interval_seconds="
        f"{interval_seconds} derived from the two newest consecutive fundingTime deltas"
    )


def fetch_btc_funding_rate_history(
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> FundingRateResult:
    """Return BTC's newest settled OKX funding rate with its derived interval."""

    params = {"instId": BTC_USDT_SWAP_INST_ID, "limit": "2"}
    try:
        response = (
            httpx.get(
                BTC_FUNDING_RATE_HISTORY_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                BTC_FUNDING_RATE_HISTORY_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
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
        rows = OkxFundingRateHistoryResponse.model_validate(response.json()).data
        if len(rows) < 2:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX returned fewer than two settled funding-rate entries",
            )

        timestamps = [int(row.funding_time) for row in rows]
        if any(newer <= older for newer, older in pairwise(timestamps)):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    "OKX funding-rate-history timestamps are not strictly ordered "
                    "newest-first"
                ),
            )

        newest = rows[0]
        interval_milliseconds = timestamps[0] - timestamps[1]
        if interval_milliseconds % 1000 != 0:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX funding interval is not an exact number of seconds",
            )
        interval_seconds = interval_milliseconds // 1000
        if interval_seconds <= 0:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX funding interval must be positive",
            )

        source_timestamp = datetime.fromtimestamp(timestamps[0] / 1000, tz=UTC)
        current_time = datetime.now(UTC) if now is None else now
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX source timestamp is in the future or present",
            )

        return FundingRateOk(
            value=float(newest.realized_rate),
            source_timestamp=source_timestamp,
            source_field=_interval_source_field(interval_seconds),
        )
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX funding-rate-history response: {error}",
        )
