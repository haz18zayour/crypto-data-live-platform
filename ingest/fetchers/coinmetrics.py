"""Fetch Coin Metrics community asset metrics."""

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic, sleep

import httpx

from ingest.schemas import CoinMetricsAssetMetricsResponse
from ingest.status import Error, Ok, Reason, Result, Unavailable

COINMETRICS_ASSET_METRICS_ENDPOINT = (
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
)
REQUEST_TIMEOUT_SECONDS = 10
COINMETRICS_MIN_REQUEST_INTERVAL_SECONDS = 0.7


class CoinMetricsRateLimiter:
    """Serialize Coin Metrics calls below the community per-IP rate limit."""

    def __init__(
        self,
        *,
        min_interval_seconds: float = COINMETRICS_MIN_REQUEST_INTERVAL_SECONDS,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_at: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                self._sleeper(remaining)
                now = self._clock()
        self._last_request_at = now


_DEFAULT_RATE_LIMITER = CoinMetricsRateLimiter()


def _coinmetrics_error_message(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    errors = payload.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        message = errors[0].get("message")
        if isinstance(message, str):
            return message
    message = payload.get("message")
    if isinstance(message, str):
        return message
    return None


def _coinmetrics_error_type(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        error_type = error.get("type")
        if isinstance(error_type, str):
            return error_type
    errors = payload.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        error_type = errors[0].get("type")
        if isinstance(error_type, str):
            return error_type
    error_type = payload.get("type")
    if isinstance(error_type, str):
        return error_type
    return None


def _parse_coinmetrics_time(value: str) -> datetime:
    normalized = value.removesuffix("Z")
    if "." in normalized:
        prefix, suffix = normalized.split(".", 1)
        normalized = f"{prefix}.{suffix[:6]}"
    return datetime.fromisoformat(normalized).replace(tzinfo=UTC)


def _fetch_asset_metric(
    asset: str,
    metric: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    asset_parameter = asset.casefold()
    params = {
        "assets": asset_parameter,
        "metrics": metric,
        "limit_per_asset": "1",
        "page_size": "1",
    }
    try:
        limiter = rate_limiter
        if limiter is None and client is None:
            limiter = _DEFAULT_RATE_LIMITER
        if limiter is not None:
            limiter.wait()
        response = (
            httpx.get(
                COINMETRICS_ASSET_METRICS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                COINMETRICS_ASSET_METRICS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Coin Metrics request failed: {error}",
        )

    payload: object
    try:
        payload = response.json()
    except ValueError:
        payload = None

    error_type = _coinmetrics_error_type(payload)
    if response.status_code == 403 and error_type in {None, "forbidden"}:
        return Unavailable(reason=Reason.PAYWALLED)
    if error_type == "bad_parameter":
        message = _coinmetrics_error_message(payload) or "bad_parameter"
        return Error(reason=Reason.FETCH_FAILED, detail=message)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Coin Metrics returned HTTP {error.response.status_code}",
        )

    try:
        rows = CoinMetricsAssetMetricsResponse.model_validate(payload).data
        if len(rows) != 1:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Coin Metrics returned an unexpected number of MVRV entries",
            )
        row = rows[0]
        if row.asset != asset_parameter:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=(
                    f"Coin Metrics returned asset {row.asset}, "
                    f"expected {asset_parameter}"
                ),
            )
        source_timestamp = _parse_coinmetrics_time(row.time)
        current_time = datetime.now(UTC) if now is None else now
        if source_timestamp >= current_time:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Coin Metrics source timestamp is in the future or present",
            )
        return Ok(value=float(row.CapMVRVCur), source_timestamp=source_timestamp)
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid Coin Metrics asset-metrics response: {error}",
        )


def _fetch_btc_metric(
    metric: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    return _fetch_asset_metric(
        "BTC",
        metric,
        client=client,
        now=now,
        rate_limiter=rate_limiter,
    )


def fetch_btc_mvrv(
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    """Return BTC's latest Coin Metrics MVRV, or an explicit absence result."""

    return fetch_mvrv(
        "BTC",
        client=client,
        now=now,
        rate_limiter=rate_limiter,
    )


def fetch_mvrv(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    """Return an asset's latest Coin Metrics MVRV, or explicit absence."""

    return _fetch_asset_metric(
        asset,
        "CapMVRVCur",
        client=client,
        now=now,
        rate_limiter=rate_limiter,
    )
