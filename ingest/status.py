"""Typed outcomes for market-data collection."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal


class Reason(StrEnum):
    """Why an indicator has no usable value."""

    NOT_DEFINABLE = "NOT_DEFINABLE"
    PAYWALLED = "PAYWALLED"
    FETCH_FAILED = "FETCH_FAILED"
    NOT_FETCHED = "NOT_FETCHED"


def _require_source_timestamp(source_timestamp: object) -> None:
    if not isinstance(source_timestamp, datetime):
        raise TypeError("source_timestamp must be a datetime")


def _require_reason(reason: object) -> None:
    if not isinstance(reason, Reason):
        raise TypeError("reason must be a Reason")


@dataclass(frozen=True, slots=True)
class Ok:
    """A current value and the time reported by its source."""

    value: float
    source_timestamp: datetime
    status: Literal["OK"] = field(default="OK", init=False)

    def __post_init__(self) -> None:
        _require_source_timestamp(self.source_timestamp)


@dataclass(frozen=True, slots=True)
class Stale:
    """A value that is older than its freshness budget."""

    value: float
    source_timestamp: datetime
    status: Literal["STALE"] = field(default="STALE", init=False)

    def __post_init__(self) -> None:
        _require_source_timestamp(self.source_timestamp)


@dataclass(frozen=True, slots=True)
class Unavailable:
    """An indicator for which no numeric value is available."""

    reason: Reason
    status: Literal["UNAVAILABLE"] = field(default="UNAVAILABLE", init=False)

    def __post_init__(self) -> None:
        _require_reason(self.reason)


@dataclass(frozen=True, slots=True)
class Error:
    """A failed attempt to obtain an indicator value."""

    reason: Reason
    detail: str
    status: Literal["ERROR"] = field(default="ERROR", init=False)

    def __post_init__(self) -> None:
        _require_reason(self.reason)


type Result = Ok | Stale | Unavailable | Error
