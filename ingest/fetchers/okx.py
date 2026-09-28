"""Fetch OKX's final UTC daily candles and candle-derived backfill rows."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Literal, NoReturn, cast

import httpx
from talib import abstract

from ingest.registry import IndicatorDefinition, load_registry
from ingest.schemas import OkxCandle, OkxCandleResponse
from ingest.status import Error, Ok, Reason, Result, Unavailable

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

INDICATOR_KEY = "btc_daily_close"
MEASURED_ON = "BTC"
REQUEST_TIMEOUT_SECONDS = 10
HISTORY_ENDPOINT = "https://www.okx.com/api/v5/market/history-candles"
HISTORY_PAGE_LIMIT = 100
BACKFILL_PLOTTED_POINTS = 90
RECURSIVE_SEED_MULTIPLE = 4

_DEFINITION = next(
    entry for entry in load_registry().root if entry.key == INDICATOR_KEY
)
ENDPOINT = _DEFINITION.endpoint
REQUIRED_BARS = cast(int, _DEFINITION.required_bars)
EXPECTED_UPDATE_INTERVAL_SECONDS = _DEFINITION.expected_update_interval_seconds


@dataclass(frozen=True, slots=True)
class BackfilledOkxValue:
    """An OKX backfilled value with runtime provenance."""

    value: float
    source_timestamp: datetime
    endpoint: str
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)


def fetch_btc_daily_bars(
    required_bars: int,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple[OkxCandle, ...] | Error:
    """Return exactly ``required_bars`` closed BTC candles, newest first."""

    current_time = datetime.now(UTC) if now is None else now
    current_bucket = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if current_bucket == current_time:
        current_bucket -= timedelta(days=1)
    cursor = int(current_bucket.timestamp() * 1000)
    rows: list[OkxCandle] = []

    while len(rows) < required_bars:
        page_size = min(HISTORY_PAGE_LIMIT, required_bars - len(rows))
        params = {
            "instId": "BTC-USDT",
            "bar": "1Dutc",
            "limit": str(page_size),
            "after": str(cursor),
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
                detail=f"OKX returned HTTP {error.response.status_code}",
            )
        except httpx.RequestError as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"OKX request failed: {error}",
            )

        try:
            page = OkxCandleResponse.model_validate(response.json()).data
            if len(page) != page_size:
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail=(
                        f"OKX page returned {len(page)} bars, expected {page_size}"
                    ),
                )
            if any(row[-1] != "1" for row in page):
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail="OKX history page contained an unconfirmed bar",
                )
            rows.extend(page)
            cursor = int(page[-1][0])
        except (IndexError, KeyError, TypeError, ValueError, OverflowError) as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Invalid OKX candle response: {error}",
            )

    try:
        timestamps = [int(row[0]) for row in rows]
        if any(newer <= older for newer, older in pairwise(timestamps)):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX candle timestamps are not strictly ordered newest-first",
            )
        interval_milliseconds = EXPECTED_UPDATE_INTERVAL_SECONDS * 1000
        if any(
            newer - older != interval_milliseconds
            for newer, older in pairwise(timestamps)
        ):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    "OKX candle timestamps are not contiguous at the expected "
                    f"{EXPECTED_UPDATE_INTERVAL_SECONDS}-second interval"
                ),
            )
        if any(
            datetime.fromtimestamp(timestamp / 1000, tz=UTC).time()
            != datetime.min.time()
            for timestamp in timestamps
        ):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX daily candle is not aligned to UTC midnight",
            )
        if len(rows) != required_bars:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"OKX returned {len(rows)} bars, expected {required_bars}",
            )
        return tuple(rows)
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX candle response: {error}",
        )


def fetch_asset_daily_history_bars(
    asset: str,
    required_bars: int,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple[OkxCandle, ...] | Error:
    """Return closed UTC daily OKX candles for one asset, newest first."""

    current_time = datetime.now(UTC) if now is None else now
    current_bucket = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if current_bucket == current_time:
        current_bucket -= timedelta(days=1)
    cursor = int(current_bucket.timestamp() * 1000)
    rows: list[OkxCandle] = []

    while len(rows) < required_bars:
        page_size = min(HISTORY_PAGE_LIMIT, required_bars - len(rows))
        params = {
            "instId": f"{asset}-USDT",
            "bar": "1Dutc",
            "limit": str(page_size),
            "after": str(cursor),
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
                detail=f"OKX returned HTTP {error.response.status_code}",
            )
        except httpx.RequestError as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"OKX request failed: {error}",
            )

        try:
            page = OkxCandleResponse.model_validate(response.json()).data
            if not page:
                break
            if any(row[-1] != "1" for row in page):
                return Error(
                    reason=Reason.FETCH_FAILED,
                    detail="OKX history page contained an unconfirmed bar",
                )
            rows.extend(page)
            cursor = int(page[-1][0])
        except (IndexError, KeyError, TypeError, ValueError, OverflowError) as error:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Invalid OKX candle response: {error}",
            )

    try:
        timestamps = [int(row[0]) for row in rows]
        if any(newer <= older for newer, older in pairwise(timestamps)):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX candle timestamps are not strictly ordered newest-first",
            )
        interval_milliseconds = EXPECTED_UPDATE_INTERVAL_SECONDS * 1000
        if any(
            newer - older != interval_milliseconds
            for newer, older in pairwise(timestamps)
        ):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX candle timestamps are not contiguous at 1Dutc",
            )
        if len(rows) < required_bars:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"OKX returned {len(rows)} bars, expected {required_bars}",
            )
        return tuple(rows[:required_bars])
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX candle response: {error}",
        )


def _backfill_seed_bars(
    required_bars: int,
    talib_function: str | None,
    parameters: dict[str, int | float] | None,
) -> int:
    if talib_function is None:
        return required_bars
    function = abstract.Function(talib_function)  # type: ignore[attr-defined]
    function.set_parameters(parameters or {})
    lookback = int(function.lookback)
    return max(required_bars, lookback * RECURSIVE_SEED_MULTIPLE + 1)


def _normalise_candles(rows: tuple[OkxCandle, ...]) -> tuple[dict[str, float], ...]:
    return tuple(
        {
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in reversed(rows)
    )


def backfill_okx_candle_indicator(
    definition: IndicatorDefinition,
    *,
    plotted_points: int = BACKFILL_PLOTTED_POINTS,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple["FullAssetRun", ...]:
    """Build one seeded historical backfill run per plotted candle."""

    from ingest.pipeline import FullAssetRun, _calculate

    required_bars = cast(int, definition.required_bars)
    seed_bars = _backfill_seed_bars(
        required_bars,
        definition.talib_function,
        definition.parameters,
    )
    total_bars = seed_bars + plotted_points - 1
    asset = definition.definable_for[0]
    rows = fetch_asset_daily_history_bars(
        asset,
        total_bars,
        client=client,
        now=now,
    )
    if isinstance(rows, Error):
        _raise_backfill_fetch_error(rows)

    bars = _normalise_candles(rows)
    oldest_first_rows = tuple(reversed(rows))
    runs: list[FullAssetRun] = []
    for end in range(seed_bars, len(bars) + 1):
        seeded = bars[end - seed_bars : end]
        opened_at = datetime.fromtimestamp(
            int(oldest_first_rows[end - 1][0]) / 1000,
            tz=UTC,
        )
        runs.append(
            FullAssetRun(
                indicators={
                    definition.key: BackfilledOkxValue(
                        value=_calculate(definition, seeded),
                        source_timestamp=opened_at + timedelta(days=1),
                        endpoint=(
                            f"{HISTORY_ENDPOINT}?instId={asset}-USDT&bar=1Dutc"
                        ),
                        source_field=(
                            f"{definition.source_field}; backfill_seed_bars="
                            f"{seed_bars}; plotted_points={plotted_points}"
                        ),
                    )
                },
                history={},
            )
        )
    return tuple(runs)


def _raise_backfill_fetch_error(error: Error) -> NoReturn:
    raise RuntimeError(error.detail)


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
        rows = OkxCandleResponse.model_validate(response.json()).data
        received_bars = len(rows)
        if received_bars < REQUIRED_BARS:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    f"OKX returned {received_bars} bars, "
                    f"expected {REQUIRED_BARS}"
                ),
            )

        timestamps = [int(row[0]) for row in rows]
        if any(newer <= older for newer, older in pairwise(timestamps)):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX candle timestamps are not strictly ordered newest-first",
            )

        closed = [row for row in rows if row[-1] == "1"]
        if not closed:
            return Unavailable(reason=Reason.FETCH_FAILED)

        interval_milliseconds = EXPECTED_UPDATE_INTERVAL_SECONDS * 1000
        closed_timestamps = [int(row[0]) for row in closed]
        if any(
            newer - older != interval_milliseconds
            for newer, older in pairwise(closed_timestamps)
        ):
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    "OKX candle timestamps are not contiguous at the expected "
                    f"{EXPECTED_UPDATE_INTERVAL_SECONDS}-second interval"
                ),
            )

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
