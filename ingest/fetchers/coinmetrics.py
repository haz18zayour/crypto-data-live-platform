"""Fetch Coin Metrics community asset metrics."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic, sleep
from typing import TYPE_CHECKING, Literal, NoReturn
from urllib.parse import parse_qs, urlparse

import httpx

from ingest.registry import IndicatorDefinition
from ingest.schemas import CoinMetricsAssetMetricsResponse
from ingest.status import Error, Ok, Reason, Result, Unavailable

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

COINMETRICS_ASSET_METRICS_ENDPOINT = (
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
)
COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT = (
    "https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics"
)
REQUEST_TIMEOUT_SECONDS = 10
COINMETRICS_MIN_REQUEST_INTERVAL_SECONDS = 0.7
BACKFILL_PAGE_SIZE = 10000


@dataclass(frozen=True, slots=True)
class BackfilledCoinMetricsOk:
    """A Coin Metrics backfilled value with entitlement-window provenance."""

    value: float
    source_timestamp: datetime
    endpoint: str
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)


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


def _get_coinmetrics_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> object:
    limiter = rate_limiter
    if limiter is None and client is None:
        limiter = _DEFAULT_RATE_LIMITER
    if limiter is not None:
        limiter.wait()
    try:
        response = (
            httpx.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if client is None
            else client.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        )
    except httpx.RequestError as error:
        raise RuntimeError(f"Coin Metrics request failed: {error}") from error

    try:
        payload = response.json()
    except ValueError:
        payload = None

    error_type = _coinmetrics_error_type(payload)
    if response.status_code == 403 and error_type in {None, "forbidden"}:
        raise RuntimeError("Coin Metrics metric is paywalled on the community tier")
    if error_type == "bad_parameter":
        raise RuntimeError(_coinmetrics_error_message(payload) or "bad_parameter")

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"Coin Metrics returned HTTP {error.response.status_code}"
        ) from error
    return payload


def _metric_parameters_from_endpoint(endpoint: str) -> tuple[str, tuple[str, ...]]:
    parsed = urlparse(endpoint)
    query = parse_qs(parsed.query)
    assets = query.get("assets") or query.get("asset")
    metrics = query.get("metrics") or query.get("metric")
    if not assets or not assets[0].strip():
        raise ValueError(f"Coin Metrics endpoint is missing assets: {endpoint}")
    if not metrics or not metrics[0].strip():
        raise ValueError(f"Coin Metrics endpoint is missing metrics: {endpoint}")
    return (
        assets[0].upper(),
        tuple(metric.strip() for metric in metrics[0].split(",") if metric.strip()),
    )


def _catalog_metric_min_times(
    asset: str,
    metrics: tuple[str, ...],
    *,
    client: httpx.Client | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> dict[str, datetime]:
    params = {"assets": asset.casefold(), "metrics": ",".join(metrics)}
    payload = _get_coinmetrics_json(
        COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT,
        params=params,
        client=client,
        rate_limiter=rate_limiter,
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise TypeError("Invalid Coin Metrics catalog-v2 response")

    found: dict[str, datetime] = {}
    for asset_entry in payload["data"]:
        if not isinstance(asset_entry, dict):
            continue
        if str(asset_entry.get("asset", "")).casefold() != asset.casefold():
            continue
        metric = asset_entry.get("metric")
        if metric in metrics:
            min_time = _catalog_frequency_min_time(asset_entry)
            if min_time is not None:
                found[str(metric)] = min_time
        catalog_metrics = asset_entry.get("metrics")
        if not isinstance(catalog_metrics, list):
            continue
        for metric_entry in catalog_metrics:
            if not isinstance(metric_entry, dict):
                continue
            metric = metric_entry.get("metric")
            if metric not in metrics:
                continue
            min_time = _catalog_frequency_min_time(metric_entry)
            if min_time is not None:
                found[str(metric)] = min_time

    missing = sorted(set(metrics) - found.keys())
    if missing:
        raise RuntimeError(
            f"Coin Metrics catalog-v2 omitted min_time for {asset} {missing}"
        )
    return found


def _catalog_frequency_min_time(metric_entry: dict[object, object]) -> datetime | None:
    raw_min_time = metric_entry.get("min_time")
    if isinstance(raw_min_time, str):
        return _parse_coinmetrics_time(raw_min_time)
    frequencies = metric_entry.get("frequencies")
    if not isinstance(frequencies, list):
        return None
    daily = next(
        (
            frequency
            for frequency in frequencies
            if isinstance(frequency, dict) and frequency.get("frequency") == "1d"
        ),
        None,
    )
    if daily is None:
        daily = next(
            (frequency for frequency in frequencies if isinstance(frequency, dict)),
            None,
        )
    if isinstance(daily, dict) and isinstance(daily.get("min_time"), str):
        return _parse_coinmetrics_time(daily["min_time"])
    return None


def _history_rows(
    asset: str,
    metrics: tuple[str, ...],
    *,
    start_time: datetime,
    catalog_min_times: dict[str, datetime],
    client: httpx.Client | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> tuple[object, ...]:
    entitlement_start = max(catalog_min_times.values())
    if start_time < entitlement_start:
        raise ValueError(
            "Coin Metrics start_time precedes catalog-v2 entitlement min_time: "
            f"{start_time.isoformat()} < {entitlement_start.isoformat()}"
        )

    params = {
        "assets": asset.casefold(),
        "metrics": ",".join(metrics),
        "start_time": start_time.isoformat().replace("+00:00", "Z"),
        "page_size": str(BACKFILL_PAGE_SIZE),
    }
    next_page_url: str | None = COINMETRICS_ASSET_METRICS_ENDPOINT
    next_params: dict[str, str] | None = params
    rows: list[object] = []

    while next_page_url is not None:
        payload = _get_coinmetrics_json(
            next_page_url,
            params=next_params,
            client=client,
            rate_limiter=rate_limiter,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise TypeError("Invalid Coin Metrics asset-metrics response")
        rows.extend(payload["data"])
        raw_next = payload.get("next_page_url")
        next_page_url = raw_next if isinstance(raw_next, str) and raw_next else None
        next_params = None
    return tuple(rows)


def _value_from_backfill_row(row: object, metrics: tuple[str, ...]) -> float:
    if not isinstance(row, dict):
        raise TypeError("Invalid Coin Metrics asset-metrics row")
    if metrics == ("FlowInExNtv", "FlowOutExNtv"):
        flow_in = row.get("FlowInExNtv")
        flow_out = row.get("FlowOutExNtv")
        if flow_in is None or flow_out is None:
            raise RuntimeError(
                "Coin Metrics response omitted FlowInExNtv or FlowOutExNtv"
            )
        return float(flow_in) - float(flow_out)
    metric = metrics[0]
    raw_value = row.get(metric)
    if raw_value is None:
        raise RuntimeError(f"Coin Metrics response omitted {metric}")
    return float(raw_value)


def _runs_for(
    definition: IndicatorDefinition,
    values: list[BackfilledCoinMetricsOk],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={definition.key: value}, history={})
        for value in values
    )


def _raise_backfill_fetch_error(error: Exception) -> NoReturn:
    raise RuntimeError(str(error)) from error


def backfill_coinmetrics_asset_metrics(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> tuple["FullAssetRun", ...]:
    """Backfill a Coin Metrics daily metric from its catalog-v2 entitlement start."""

    try:
        asset, metrics = _metric_parameters_from_endpoint(definition.endpoint)
        catalog_min_times = _catalog_metric_min_times(
            asset,
            metrics,
            client=client,
            rate_limiter=rate_limiter,
        )
        entitlement_start = max(catalog_min_times.values())
        raw_rows = _history_rows(
            asset,
            metrics,
            start_time=entitlement_start,
            catalog_min_times=catalog_min_times,
            client=client,
            rate_limiter=rate_limiter,
        )
        rows = CoinMetricsAssetMetricsResponse.model_validate(
            {"data": raw_rows}
        ).data
        values: list[BackfilledCoinMetricsOk] = []
        for row in rows:
            if row.asset != asset.casefold():
                raise RuntimeError(
                    f"Coin Metrics returned asset {row.asset}, expected {asset.casefold()}"
                )
            value = _value_from_backfill_row(row.model_dump(by_alias=True), metrics)
            values.append(
                BackfilledCoinMetricsOk(
                    value=value,
                    source_timestamp=_parse_coinmetrics_time(row.time),
                    endpoint=(
                        f"{COINMETRICS_ASSET_METRICS_ENDPOINT}?assets={asset.casefold()}"
                        f"&metrics={','.join(metrics)}&start_time="
                        f"{entitlement_start.isoformat().replace('+00:00', 'Z')}"
                        f"&page_size={BACKFILL_PAGE_SIZE}"
                    ),
                    source_field=(
                        f"{definition.source_field}; catalog-v2 min_time "
                        f"{', '.join(f'{metric}={catalog_min_times[metric].isoformat()}' for metric in metrics)}"
                    ),
                )
            )
    except (
        RuntimeError,
        TypeError,
        ValueError,
        OverflowError,
        httpx.HTTPError,
    ) as error:
        _raise_backfill_fetch_error(error)
    return _runs_for(definition, values)


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
                detail=(
                    f"Coin Metrics returned an unexpected number of {metric} entries"
                ),
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
        raw_value = getattr(row, metric, None)
        if raw_value is None:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"Coin Metrics response omitted {metric}",
            )
        return Ok(value=float(raw_value), source_timestamp=source_timestamp)
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


def fetch_active_addresses(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    """Return an asset's latest Coin Metrics active-address count, or absence."""

    return _fetch_asset_metric(
        asset,
        "AdrActCnt",
        client=client,
        now=now,
        rate_limiter=rate_limiter,
    )


def fetch_exchange_flow(
    asset: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    rate_limiter: CoinMetricsRateLimiter | None = None,
) -> Result:
    """Return latest net exchange flow, inflow minus outflow, or absence."""

    asset_parameter = asset.casefold()
    params = {
        "assets": asset_parameter,
        "metrics": "FlowInExNtv,FlowOutExNtv",
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

    try:
        payload: object = response.json()
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
                detail=(
                    "Coin Metrics returned an unexpected number of "
                    "FlowInExNtv/FlowOutExNtv entries"
                ),
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
        if row.FlowInExNtv is None or row.FlowOutExNtv is None:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="Coin Metrics response omitted FlowInExNtv or FlowOutExNtv",
            )
        return Ok(
            value=float(row.FlowInExNtv) - float(row.FlowOutExNtv),
            source_timestamp=source_timestamp,
        )
    except (TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid Coin Metrics asset-metrics response: {error}",
        )
