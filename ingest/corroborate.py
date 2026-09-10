"""Preconditions for comparing values from independent venues."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class TimestampMismatch:
    """Two valid source timestamps that do not describe the same UTC day."""

    source_a_timestamp: datetime
    source_b_timestamp: datetime
    outcome: Literal["TIMESTAMP_MISMATCH"] = field(
        default="TIMESTAMP_MISMATCH", init=False
    )


def _validate_source_timestamp(
    timestamp: datetime,
    *,
    source: str,
    now: datetime,
) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{source} timestamp must be timezone-aware")

    utc_timestamp = timestamp.astimezone(UTC)
    if (
        utc_timestamp.hour,
        utc_timestamp.minute,
        utc_timestamp.second,
        utc_timestamp.microsecond,
    ) != (0, 0, 0, 0):
        raise ValueError(
            f"{source} timestamp must be on a UTC midnight boundary: "
            f"{timestamp.isoformat()}"
        )

    if timestamp > now:
        raise ValueError(
            f"{source} timestamp cannot be in the future: {timestamp.isoformat()}"
        )


def gate_timestamp_comparison[ComparisonResult](
    source_a_timestamp: datetime,
    source_b_timestamp: datetime,
    *,
    compare: Callable[[], ComparisonResult],
    now: datetime | None = None,
) -> ComparisonResult | TimestampMismatch:
    """Run ``compare`` only for equal, past, UTC-midnight timestamps."""

    current_time = datetime.now(UTC) if now is None else now
    _validate_source_timestamp(
        source_a_timestamp,
        source="source_a",
        now=current_time,
    )
    _validate_source_timestamp(
        source_b_timestamp,
        source="source_b",
        now=current_time,
    )

    if source_a_timestamp != source_b_timestamp:
        return TimestampMismatch(
            source_a_timestamp=source_a_timestamp,
            source_b_timestamp=source_b_timestamp,
        )

    return compare()
