"""Fetch OKX settled derivatives metrics."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from time import sleep
from typing import TYPE_CHECKING, Literal, NoReturn, cast

import httpx

from ingest.registry import IndicatorDefinition
from ingest.schemas import (
    OkxFundingRateHistoryResponse,
    OkxLongShortRatioResponse,
    OkxOpenInterestHistoryResponse,
    OkxOpenInterestResponse,
    OkxTakerVolumeResponse,
)
from ingest.status import Error, Reason

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

BTC_FUNDING_RATE_HISTORY_ENDPOINT = (
    "https://www.okx.com/api/v5/public/funding-rate-history"
)
OKX_OPEN_INTEREST_ENDPOINT = "https://www.okx.com/api/v5/public/open-interest"
OKX_OPEN_INTEREST_HISTORY_ENDPOINT = (
    "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history"
)
OKX_LONG_SHORT_RATIO_ENDPOINT = (
    "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio"
)
OKX_TAKER_VOLUME_ENDPOINT = "https://www.okx.com/api/v5/rubik/stat/taker-volume"
BTC_USDT_SWAP_INST_ID = "BTC-USDT-SWAP"
REQUEST_TIMEOUT_SECONDS = 10
LIVE_SOURCE_CLOCK_WAIT_SECONDS = 5
BACKFILL_PAGE_LIMIT = 100
BACKFILL_PERIOD = "1D"
RUBIK_DAILY_PERIOD_PROVENANCE = (
    "period=1D raw daily history; OKX rubik exposes no committed 1Dutc "
    "parameter here, so bucket timestamps are persisted exactly as returned"
)


@dataclass(frozen=True, slots=True)
class BackfilledOkxDerivativeOk:
    """A backfilled OKX derivatives value with its history endpoint named."""

    value: float
    source_timestamp: datetime
    endpoint: str
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)


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


@dataclass(frozen=True, slots=True)
class OpenInterestOk:
    """A USDT-margined open-interest value reported by OKX."""

    value: float
    source_timestamp: datetime
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_timestamp, datetime):
            raise TypeError("source_timestamp must be a datetime")


type OpenInterestResult = OpenInterestOk | Error


@dataclass(frozen=True, slots=True)
class LongShortRatioOk:
    """A long/short account ratio reported by OKX."""

    value: float
    source_timestamp: datetime
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_timestamp, datetime):
            raise TypeError("source_timestamp must be a datetime")


type LongShortRatioResult = LongShortRatioOk | Error


@dataclass(frozen=True, slots=True)
class TakerRatioOk:
    """A taker buy/sell volume ratio reported by OKX."""

    value: float
    source_timestamp: datetime
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_timestamp, datetime):
            raise TypeError("source_timestamp must be a datetime")


type TakerRatioResult = TakerRatioOk | Error


def _interval_source_field(interval_seconds: int) -> str:
    return (
        "OKX funding-rate-history realizedRate; interval_seconds="
        f"{interval_seconds} derived from the two newest consecutive fundingTime deltas"
    )


def _get_okx_json(
    endpoint: str,
    params: dict[str, str],
    client: httpx.Client | None,
) -> object | Error:
    try:
        response = (
            httpx.get(endpoint, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if client is None
            else client.get(endpoint, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        )
        response.raise_for_status()
        return cast(object, response.json())
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"OKX returned HTTP {error.response.status_code}",
        )
    except httpx.RequestError as error:
        return Error(reason=Reason.FETCH_FAILED, detail=f"OKX request failed: {error}")


def _runs_for(
    definition: IndicatorDefinition,
    values: list[BackfilledOkxDerivativeOk],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={definition.key: value}, history={})
        for value in values
    )


def _raise_backfill_fetch_error(error: Error) -> NoReturn:
    raise RuntimeError(error.detail)


def backfill_okx_funding_rate(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    asset = definition.definable_for[0]
    params = {
        "instId": f"{asset}-USDT-SWAP",
        "limit": str(BACKFILL_PAGE_LIMIT),
        "before": "1",
    }
    payload = _get_okx_json(BTC_FUNDING_RATE_HISTORY_ENDPOINT, params, client)
    if isinstance(payload, Error):
        _raise_backfill_fetch_error(payload)
    try:
        rows = OkxFundingRateHistoryResponse.model_validate(payload).data
        values = [
            BackfilledOkxDerivativeOk(
                value=float(row.realized_rate),
                source_timestamp=datetime.fromtimestamp(
                    int(row.funding_time) / 1000,
                    tz=UTC,
                ),
                endpoint=(
                    f"{BTC_FUNDING_RATE_HISTORY_ENDPOINT}?instId={asset}-USDT-SWAP"
                    f"&limit={BACKFILL_PAGE_LIMIT}&before=1"
                ),
                source_field=(
                    "OKX funding-rate-history realizedRate; vendor-bounded "
                    "backfill page, no synthetic earlier rows"
                ),
            )
            for row in rows
        ]
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"Invalid OKX funding-rate-history response: {error}") from error
    return _runs_for(definition, values)


def backfill_okx_open_interest(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    asset = definition.definable_for[0]
    params = {
        "instId": f"{asset}-USDT-SWAP",
        "period": BACKFILL_PERIOD,
        "limit": str(BACKFILL_PAGE_LIMIT),
    }
    payload = _get_okx_json(OKX_OPEN_INTEREST_HISTORY_ENDPOINT, params, client)
    if isinstance(payload, Error):
        _raise_backfill_fetch_error(payload)
    try:
        rows = OkxOpenInterestHistoryResponse.model_validate(payload).data
        values = [
            BackfilledOkxDerivativeOk(
                value=float(row[3]),
                source_timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                endpoint=(
                    f"{OKX_OPEN_INTEREST_HISTORY_ENDPOINT}?instId={asset}-USDT-SWAP"
                    f"&period={BACKFILL_PERIOD}&limit={BACKFILL_PAGE_LIMIT}"
                ),
                source_field=(
                    "OKX rubik/stat/contracts/open-interest-history "
                    f"period={BACKFILL_PERIOD} [ts, oi, oiCcy, oiUsd]; oiUsd"
                ),
            )
            for row in rows
        ]
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"Invalid OKX open-interest-history response: {error}") from error
    return _runs_for(definition, values)


def backfill_okx_long_short_ratio(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    asset = definition.definable_for[0]
    params = {"ccy": asset, "period": BACKFILL_PERIOD}
    payload = _get_okx_json(OKX_LONG_SHORT_RATIO_ENDPOINT, params, client)
    if isinstance(payload, Error):
        _raise_backfill_fetch_error(payload)
    try:
        rows = OkxLongShortRatioResponse.model_validate(payload).data
        values = [
            BackfilledOkxDerivativeOk(
                value=float(row[1]),
                source_timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                endpoint=(
                    f"{OKX_LONG_SHORT_RATIO_ENDPOINT}?ccy={asset}"
                    f"&period={BACKFILL_PERIOD}"
                ),
                source_field=(
                    "OKX rubik/stat/contracts/long-short-account-ratio "
                    f"{RUBIK_DAILY_PERIOD_PROVENANCE}; no resampling"
                ),
            )
            for row in rows
        ]
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"Invalid OKX long/short history response: {error}") from error
    return _runs_for(definition, values)


def backfill_okx_taker_ratio(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    asset = definition.definable_for[0]
    params = {"ccy": asset, "instType": "CONTRACTS", "period": BACKFILL_PERIOD}
    payload = _get_okx_json(OKX_TAKER_VOLUME_ENDPOINT, params, client)
    if isinstance(payload, Error):
        _raise_backfill_fetch_error(payload)
    try:
        rows = OkxTakerVolumeResponse.model_validate(payload).data
        values = [
            BackfilledOkxDerivativeOk(
                value=float(row[2]) / float(row[1]),
                source_timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                endpoint=(
                    f"{OKX_TAKER_VOLUME_ENDPOINT}?ccy={asset}&instType=CONTRACTS"
                    f"&period={BACKFILL_PERIOD}"
                ),
                source_field=(
                    "OKX rubik/stat/taker-volume "
                    f"{RUBIK_DAILY_PERIOD_PROVENANCE} "
                    "[ts, sellVol, buyVol]; ratio = buyVol / sellVol; no resampling"
                ),
            )
            for row in rows
        ]
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise RuntimeError(f"Invalid OKX taker-volume history response: {error}") from error
    return _runs_for(definition, values)


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


def fetch_open_interest(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> OpenInterestResult:
    """Return OKX open interest for one linear USDT-margined perpetual."""

    inst_id = f"{asset}-USDT-SWAP"
    params = {"instType": "SWAP", "instId": inst_id}
    try:
        response = (
            httpx.get(
                OKX_OPEN_INTEREST_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                OKX_OPEN_INTEREST_ENDPOINT,
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
        rows = OkxOpenInterestResponse.model_validate(response.json()).data
        if len(rows) != 1:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX returned an unexpected number of open-interest entries",
            )

        row = rows[0]
        source_timestamp = datetime.fromtimestamp(int(row.ts) / 1000, tz=UTC)
        current_time = datetime.now(UTC) if now is None else now
        wait_seconds = (source_timestamp - current_time).total_seconds()
        if now is None and 0 <= wait_seconds <= LIVE_SOURCE_CLOCK_WAIT_SECONDS:
            sleep(wait_seconds + 0.001)
            current_time = datetime.now(UTC)
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX source timestamp is in the future or present",
            )

        return OpenInterestOk(
            value=float(row.oi_usd),
            source_timestamp=source_timestamp,
        )
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX open-interest response: {error}",
        )


def fetch_long_short_ratio(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> LongShortRatioResult:
    """Return OKX's newest long/short account ratio for one asset."""

    params = {"ccy": asset, "period": "5m"}
    try:
        response = (
            httpx.get(
                OKX_LONG_SHORT_RATIO_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                OKX_LONG_SHORT_RATIO_ENDPOINT,
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
        rows = OkxLongShortRatioResponse.model_validate(response.json()).data
        if not rows:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX returned no long/short account-ratio entries",
            )

        newest = max(rows, key=lambda row: int(row[0]))
        source_timestamp = datetime.fromtimestamp(int(newest[0]) / 1000, tz=UTC)
        current_time = datetime.now(UTC) if now is None else now
        wait_seconds = (source_timestamp - current_time).total_seconds()
        if now is None and 0 <= wait_seconds <= LIVE_SOURCE_CLOCK_WAIT_SECONDS:
            sleep(wait_seconds + 0.001)
            current_time = datetime.now(UTC)
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX source timestamp is in the future or present",
            )

        return LongShortRatioOk(
            value=float(newest[1]),
            source_timestamp=source_timestamp,
        )
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX long/short account-ratio response: {error}",
        )


def fetch_taker_ratio(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> TakerRatioResult:
    """Return OKX's newest taker buy/sell volume ratio for one asset."""

    params = {"ccy": asset, "instType": "CONTRACTS", "period": "5m"}
    try:
        response = (
            httpx.get(
                OKX_TAKER_VOLUME_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                OKX_TAKER_VOLUME_ENDPOINT,
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
        rows = OkxTakerVolumeResponse.model_validate(response.json()).data
        if not rows:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX returned no taker-volume entries",
            )

        newest = max(rows, key=lambda row: int(row[0]))
        source_timestamp = datetime.fromtimestamp(int(newest[0]) / 1000, tz=UTC)
        current_time = datetime.now(UTC) if now is None else now
        wait_seconds = (source_timestamp - current_time).total_seconds()
        if now is None and 0 <= wait_seconds <= LIVE_SOURCE_CLOCK_WAIT_SECONDS:
            sleep(wait_seconds + 0.001)
            current_time = datetime.now(UTC)
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX source timestamp is in the future or present",
            )

        sell_volume = float(newest[1])
        buy_volume = float(newest[2])
        if sell_volume <= 0:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="OKX taker sell volume must be positive to compute a ratio",
            )

        return TakerRatioOk(
            value=buy_volume / sell_volume,
            source_timestamp=source_timestamp,
        )
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid OKX taker-volume response: {error}",
        )
