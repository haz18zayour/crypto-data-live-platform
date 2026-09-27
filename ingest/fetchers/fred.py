"""Fetch FRED macro observations with their real initial publication date."""

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

import httpx
from pydantic import ValidationError

from ingest.schemas import FredObservation, FredSeriesObservationsResponse
from ingest.status import Error, Reason

FRED_SERIES_OBSERVATIONS_ENDPOINT = (
    "https://api.stlouisfed.org/fred/series/observations"
)
REQUEST_TIMEOUT_SECONDS = 10
EARLIEST_REALTIME_START = "1776-07-04"
LATEST_REALTIME_END = "9999-12-31"
FRED_VALUE_FIELD = "FRED series/observations value; output_type=4 realtime_start"


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


def _api_key() -> str | None:
    token = os.environ.get("FRED_API_KEY")
    if token is None or not token.strip():
        return None
    return token.strip()


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

    params = {
        "series_id": series.series_id,
        "api_key": token,
        "file_type": "json",
        "output_type": "4",
        "realtime_start": EARLIEST_REALTIME_START,
        "realtime_end": LATEST_REALTIME_END,
        "order_by": "observation_date",
        "sort_order": "desc",
        "limit": "10",
    }
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
