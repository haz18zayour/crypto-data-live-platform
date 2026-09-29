"""Fetch FRED macro observations with their real initial publication date."""

import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal, NoReturn
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import ValidationError

from ingest.schemas import FredObservation, FredSeriesObservationsResponse
from ingest.status import Error, Reason

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun
    from ingest.registry import IndicatorDefinition

FRED_SERIES_OBSERVATIONS_ENDPOINT = (
    "https://api.stlouisfed.org/fred/series/observations"
)
REQUEST_TIMEOUT_SECONDS = 10
# Confirmed live, 2026-09-28: a realtime_start this far back makes FRED enumerate every
# vintage date in the window before it can filter to the initial release. For a daily
# series (VIXCLS, DFF, T10Y2Y, DFII10) that history exceeds 3000 vintage dates and FRED
# 400s with "exceeds the maximum number of vintage dates allowed (2000)". We only ever
# want the initial release of the newest few observations (limit=10, sort_order=desc), so
# a window of a couple of years comfortably covers any revision to a recent observation
# while staying far under the cap - verified to return identical values to the full
# 1776-9999 range for the three low-frequency series that happened to fit under it.
REALTIME_WINDOW_DAYS = 730
LATEST_REALTIME_END = "9999-12-31"
FRED_VALUE_FIELD = "FRED series/observations value; output_type=4 realtime_start"
FRED_BACKFILL_START = date(1947, 1, 1)
FRED_BACKFILL_CHUNK_DAYS = 365
FRED_BACKFILL_LIMIT = 100000


@dataclass(frozen=True, slots=True)
class FredSeries:
    """A FRED series entry for the shared fetcher."""

    series_id: str
    source_field: str = FRED_VALUE_FIELD

    def __post_init__(self) -> None:
        if not self.series_id.strip():
            raise ValueError("series_id must be non-empty")
        if not self.source_field.strip():
            raise ValueError("source_field must be non-empty")


@dataclass(frozen=True, slots=True)
class FredOk:
    """A FRED value plus the observation period and publication date."""

    value: float
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.reference_period.strip():
            raise ValueError("reference_period must be non-empty")
        if not self.source_field.strip():
            raise ValueError("source_field must be non-empty")


type FredResult = FredOk | Error


@dataclass(frozen=True, slots=True)
class BackfilledFredOk:
    """A historical FRED initial-release value plus its publication semantics."""

    value: float
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    endpoint: str
    source_field: str
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.reference_period.strip():
            raise ValueError("reference_period must be non-empty")
        if not self.endpoint.strip():
            raise ValueError("endpoint must be non-empty")
        if not self.source_field.strip():
            raise ValueError("source_field must be non-empty")


def _api_key() -> str | None:
    token = os.environ.get("FRED_API_KEY")
    if token is None or not token.strip():
        return None
    return token.strip()


def _series_id_from_endpoint(endpoint: str) -> str:
    values = parse_qs(urlparse(endpoint).query).get("series_id")
    if not values or not values[0].strip():
        raise ValueError(f"FRED endpoint is missing series_id: {endpoint}")
    return values[0]


def _parse_fred_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _parse_observation_value(row: FredObservation) -> Decimal | None:
    if row.value == ".":
        return None
    try:
        return Decimal(row.value)
    except InvalidOperation as error:
        raise ValueError(f"FRED value is not numeric: {row.value}") from error


def _revision_source_field(
    source_field: str,
    *,
    current_value: Decimal,
    previous_observation_value: str | None,
    previous_reference_period: str | None,
    reference_period: str,
) -> str:
    if (
        previous_observation_value is None
        or previous_reference_period != reference_period
    ):
        return source_field
    try:
        previous_value = Decimal(previous_observation_value)
    except InvalidOperation as error:
        raise ValueError(
            f"previous_observation_value is not numeric: {previous_observation_value}"
        ) from error
    if previous_value == current_value:
        return source_field
    return f"{source_field}; revised from {previous_observation_value}"


def _date_chunks(
    start: date,
    end: date,
    *,
    chunk_days: int = FRED_BACKFILL_CHUNK_DAYS,
) -> tuple[tuple[date, date], ...]:
    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    if end < start:
        return ()

    chunks: list[tuple[date, date]] = []
    current_start = start
    while current_start <= end:
        current_end = min(end, current_start + timedelta(days=chunk_days - 1))
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return tuple(chunks)


def _fred_observation_params(
    series_id: str,
    token: str,
    *,
    realtime_start: date | str,
    realtime_end: date | str,
    sort_order: str,
    limit: int,
) -> dict[str, str]:
    start = (
        realtime_start.isoformat()
        if isinstance(realtime_start, date)
        else realtime_start
    )
    end = realtime_end.isoformat() if isinstance(realtime_end, date) else realtime_end
    return {
        "series_id": series_id,
        "api_key": token,
        "file_type": "json",
        "output_type": "4",
        "realtime_start": start,
        "realtime_end": end,
        "order_by": "observation_date",
        "sort_order": sort_order,
        "limit": str(limit),
    }


class FredAlfredUnavailableError(RuntimeError):
    """FRED has no vintage archive at all for this realtime_start/end window.

    Confirmed live, 2026-09-28: requesting output_type=4 for a chunk entirely before a
    series' ALFRED (vintage) archive begins returns this exact 400, distinct from every
    other failure mode - it is a real, permanent boundary of the series' own history, not
    a transient error. VIXCLS's ALFRED archive does not reach back to 1990 even though the
    live VIX index itself is far older.
    """


def _get_fred_observations(
    params: dict[str, str],
    *,
    client: httpx.Client | None = None,
) -> FredSeriesObservationsResponse:
    try:
        response = (
            httpx.get(
                FRED_SERIES_OBSERVATIONS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                FRED_SERIES_OBSERVATIONS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        raise RuntimeError(f"FRED request failed: {error.__class__.__name__}") from error

    if response.status_code == 400:
        try:
            body = response.json()
        except ValueError:
            body = {}
        if "does not exist in ALFRED" in str(body.get("error_message", "")):
            raise FredAlfredUnavailableError(
                "FRED has no ALFRED vintage archive for this realtime window"
            )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise RuntimeError(f"FRED returned HTTP {error.response.status_code}") from error

    payload = FredSeriesObservationsResponse.model_validate(response.json())
    if payload.output_type != 4:
        raise RuntimeError(f"FRED returned output_type {payload.output_type}, expected 4")
    return payload


def _runs_for(
    definition: "IndicatorDefinition",
    values: list[BackfilledFredOk],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={definition.key: value}, history={})
        for value in values
    )


def _raise_backfill_fetch_error(error: Exception) -> NoReturn:
    raise RuntimeError(str(error)) from error


def backfill_fred_initial_release(
    definition: "IndicatorDefinition",
    *,
    client: httpx.Client | None = None,
    api_key: str | None = None,
    start_date: date = FRED_BACKFILL_START,
    end_date: date | None = None,
    chunk_days: int = FRED_BACKFILL_CHUNK_DAYS,
) -> tuple["FullAssetRun", ...]:
    """Backfill FRED history with the same output_type=4 semantics as live."""

    token = _api_key() if api_key is None else api_key.strip()
    if not token:
        raise RuntimeError("FRED_API_KEY is not configured")

    series_id = _series_id_from_endpoint(definition.endpoint)
    final_date = datetime.now(UTC).date() if end_date is None else end_date
    previous_by_reference_period: dict[str, str] = {}
    values: list[BackfilledFredOk] = []

    try:
        for realtime_start, realtime_end in _date_chunks(
            start_date,
            final_date,
            chunk_days=chunk_days,
        ):
            params = _fred_observation_params(
                series_id,
                token,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                sort_order="asc",
                limit=FRED_BACKFILL_LIMIT,
            )
            try:
                payload = _get_fred_observations(params, client=client)
            except FredAlfredUnavailableError:
                # This chunk is entirely before the series' own ALFRED archive begins -
                # a real, permanent boundary of the series' history, not an error to
                # abort on. Chunks are oldest-to-newest, so later (more recent) chunks
                # may still have real vintage data even though this one does not.
                continue
            endpoint = (
                f"{FRED_SERIES_OBSERVATIONS_ENDPOINT}?series_id={series_id}"
                "&file_type=json&output_type=4"
                f"&realtime_start={realtime_start.isoformat()}"
                f"&realtime_end={realtime_end.isoformat()}"
                "&order_by=observation_date&sort_order=asc"
                f"&limit={FRED_BACKFILL_LIMIT}"
            )
            for row in payload.observations:
                value = _parse_observation_value(row)
                if value is None:
                    continue
                previous_value = previous_by_reference_period.get(row.date)
                source_field = _revision_source_field(
                    definition.source_field,
                    current_value=value,
                    previous_observation_value=previous_value,
                    previous_reference_period=(
                        row.date if previous_value is not None else None
                    ),
                    reference_period=row.date,
                )
                published_at = _parse_fred_date(row.realtime_start)
                values.append(
                    BackfilledFredOk(
                        value=float(value),
                        source_timestamp=published_at,
                        reference_period=row.date,
                        published_at=published_at,
                        endpoint=endpoint,
                        source_field=source_field,
                    )
                )
                previous_by_reference_period[row.date] = row.value
    except (
        RuntimeError,
        ValidationError,
        TypeError,
        ValueError,
        OverflowError,
        httpx.HTTPError,
    ) as error:
        _raise_backfill_fetch_error(error)

    return _runs_for(definition, values)


def fetch_fred_series(
    series: FredSeries,
    *,
    client: httpx.Client | None = None,
    api_key: str | None = None,
    previous_observation_value: str | None = None,
    previous_reference_period: str | None = None,
) -> FredResult:
    """Return the newest real FRED observation from the initial-release vintage."""

    token = _api_key() if api_key is None else api_key.strip()
    if not token:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="FRED_API_KEY is not configured",
        )

    realtime_start = (
        datetime.now(UTC) - timedelta(days=REALTIME_WINDOW_DAYS)
    ).strftime("%Y-%m-%d")
    params = _fred_observation_params(
        series.series_id,
        token,
        realtime_start=realtime_start,
        realtime_end=LATEST_REALTIME_END,
        sort_order="desc",
        limit=10,
    )
    try:
        response = (
            httpx.get(
                FRED_SERIES_OBSERVATIONS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                FRED_SERIES_OBSERVATIONS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"FRED request failed: {error.__class__.__name__}",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"FRED returned HTTP {error.response.status_code}",
        )

    try:
        payload = FredSeriesObservationsResponse.model_validate(response.json())
        if payload.output_type != 4:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail=f"FRED returned output_type {payload.output_type}, expected 4",
            )
        for row in payload.observations:
            value = _parse_observation_value(row)
            if value is None:
                continue
            published_at = _parse_fred_date(row.realtime_start)
            source_field = _revision_source_field(
                series.source_field,
                current_value=value,
                previous_observation_value=previous_observation_value,
                previous_reference_period=previous_reference_period,
                reference_period=row.date,
            )
            return FredOk(
                value=float(value),
                source_timestamp=published_at,
                reference_period=row.date,
                published_at=published_at,
                source_field=source_field,
            )
        return Error(
            reason=Reason.FETCH_FAILED,
            detail="FRED returned no real observation value",
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid FRED series/observations response: {error}",
        )
