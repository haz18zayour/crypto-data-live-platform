"""Fetch alternative.me's Crypto Fear & Greed Index."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, NoReturn

import httpx
from pydantic import ValidationError

from ingest.registry import IndicatorDefinition
from ingest.schemas import AlternativeMeFearGreedResponse
from ingest.status import Error, Reason

if TYPE_CHECKING:
    from ingest.pipeline import FullAssetRun

ALTERNATIVE_ME_FNG_ENDPOINT = "https://api.alternative.me/fng/?limit=1"
ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT = "https://api.alternative.me/fng/?limit=0"
REQUEST_TIMEOUT_SECONDS = 10
ALTERNATIVE_ME_SOURCE_FIELD = (
    "alternative.me Crypto Fear & Greed Index value; vendor's own six-weight "
    "composite: volatility 25%, momentum/volume 25%, social 15%, surveys 15% "
    "currently paused, dominance 10%, Google Trends 10%; attribution: Data "
    "provided by alternative.me"
)


@dataclass(frozen=True, slots=True)
class AlternativeMeFearGreedOk:
    """A Fear & Greed value with alternative.me provenance and disclosure."""

    value: int
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    value_classification: str
    source_field: str = ALTERNATIVE_ME_SOURCE_FIELD
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.reference_period.strip():
            raise ValueError("reference_period must be non-empty")
        if not self.value_classification.strip():
            raise ValueError("value_classification must be non-empty")
        if not self.source_field.strip():
            raise ValueError("source_field must be non-empty")


type AlternativeMeFearGreedResult = AlternativeMeFearGreedOk | Error


@dataclass(frozen=True, slots=True)
class BackfilledAlternativeMeFearGreedOk:
    """A historical Fear & Greed value without the vendor verdict label."""

    value: int
    source_timestamp: datetime
    reference_period: str
    published_at: datetime
    source_field: str = ALTERNATIVE_ME_SOURCE_FIELD
    # The registry's static endpoint hardcodes ?limit=1 (the live query); backfill
    # actually calls ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT (?limit=0), a different URL,
    # so this must be set explicitly rather than left to persist_board's live fallback.
    endpoint: str | None = None
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


def _parse_value(value: str) -> int:
    parsed = int(value)
    if parsed < 0 or parsed > 100:
        raise ValueError(f"alternative.me Fear & Greed value is out of range: {value}")
    return parsed


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)


def _runs_for(
    definition: IndicatorDefinition,
    values: list[BackfilledAlternativeMeFearGreedOk],
) -> tuple["FullAssetRun", ...]:
    from ingest.pipeline import FullAssetRun

    return tuple(
        FullAssetRun(indicators={definition.key: value}, history={})
        for value in values
    )


def _raise_backfill_fetch_error(error: Exception) -> NoReturn:
    raise RuntimeError(str(error)) from error


def backfill_alternative_me_fear_greed(
    definition: IndicatorDefinition,
    *,
    client: httpx.Client | None = None,
) -> tuple["FullAssetRun", ...]:
    """Backfill historical Fear & Greed values, excluding verdict labels."""

    try:
        response = (
            httpx.get(
                ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
        response.raise_for_status()
        rows = AlternativeMeFearGreedResponse.model_validate(response.json()).data
        values: list[BackfilledAlternativeMeFearGreedOk] = []
        for row in rows:
            timestamp = _parse_timestamp(row.timestamp)
            values.append(
                BackfilledAlternativeMeFearGreedOk(
                    value=_parse_value(row.value),
                    source_timestamp=timestamp,
                    reference_period=timestamp.date().isoformat(),
                    published_at=timestamp,
                    endpoint=ALTERNATIVE_ME_FNG_HISTORY_ENDPOINT,
                )
            )
    except (
        httpx.HTTPError,
        ValidationError,
        TypeError,
        ValueError,
        OverflowError,
    ) as error:
        _raise_backfill_fetch_error(error)
    return _runs_for(definition, values)


def fetch_fear_greed_index(
    *,
    client: httpx.Client | None = None,
) -> AlternativeMeFearGreedResult:
    """Return the newest alternative.me Fear & Greed Index value."""

    try:
        response = (
            httpx.get(
                ALTERNATIVE_ME_FNG_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if client is None
            else client.get(
                ALTERNATIVE_ME_FNG_ENDPOINT,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
    except httpx.RequestError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"alternative.me request failed: {error.__class__.__name__}",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"alternative.me returned HTTP {error.response.status_code}",
        )

    try:
        payload = AlternativeMeFearGreedResponse.model_validate(response.json())
        if not payload.data:
            return Error(
                reason=Reason.FETCH_FAILED,
                detail="alternative.me returned no Fear & Greed rows",
            )
        row = payload.data[0]
        timestamp = _parse_timestamp(row.timestamp)
        return AlternativeMeFearGreedOk(
            value=_parse_value(row.value),
            source_timestamp=timestamp,
            reference_period=timestamp.date().isoformat(),
            published_at=timestamp,
            value_classification=row.value_classification,
        )
    except (ValidationError, TypeError, ValueError, OverflowError) as error:
        return Error(
            reason=Reason.FETCH_FAILED,
            detail=f"Invalid alternative.me Fear & Greed response: {error}",
        )
