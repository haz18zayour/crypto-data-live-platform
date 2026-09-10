"""Preconditions for comparing values from independent venues."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, cast

import psycopg

from ingest.fetchers import coinbase, okx
from ingest.persist import persist_datapoint
from ingest.registry import IndicatorDefinition, load_registry
from ingest.status import Ok

CorroborationStatus = Literal["CORROBORATED", "DIVERGED"]


@dataclass(frozen=True, slots=True)
class DivergenceAssessment:
    """The comparison only; venue values remain on their own datapoint rows."""

    divergence_bps: float
    tolerance_bps_at_write: float
    status: CorroborationStatus


@dataclass(frozen=True, slots=True)
class CorroborationRecord:
    """A persisted comparison linking two peer datapoint rows."""

    id: int
    datapoint_a_id: int
    datapoint_b_id: int
    divergence_bps: float
    tolerance_bps_at_write: float
    status: CorroborationStatus


@dataclass(frozen=True, slots=True)
class TimestampMismatch:
    """Two valid source timestamps that do not describe the same UTC day."""

    source_a_timestamp: datetime
    source_b_timestamp: datetime
    outcome: Literal["TIMESTAMP_MISMATCH"] = field(
        default="TIMESTAMP_MISMATCH", init=False
    )


def compute_divergence_bps(source_a_value: float, source_b_value: float) -> float:
    """Return absolute venue disagreement relative to their midpoint."""

    midpoint = (source_a_value + source_b_value) / 2
    return abs(source_a_value - source_b_value) / midpoint * 10_000


def assess_divergence(
    definition: IndicatorDefinition,
    source_a_value: float,
    source_b_value: float,
) -> DivergenceAssessment:
    """Judge a comparison using this indicator's registry tolerance."""

    if definition.corroboration is None:
        raise ValueError(f"{definition.key} has no corroboration definition")

    divergence_bps = compute_divergence_bps(source_a_value, source_b_value)
    tolerance_bps = definition.corroboration.tolerance_bps
    status: CorroborationStatus = (
        "CORROBORATED" if divergence_bps <= tolerance_bps else "DIVERGED"
    )
    return DivergenceAssessment(
        divergence_bps=divergence_bps,
        tolerance_bps_at_write=tolerance_bps,
        status=status,
    )


def record_corroboration(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    definition: IndicatorDefinition,
    datapoint_a_id: int,
    source_a_value: float,
    datapoint_b_id: int,
    source_b_value: float,
) -> CorroborationRecord:
    """Persist the first judgment for a pair without re-judging it later."""

    assessment = assess_divergence(definition, source_a_value, source_b_value)
    first_id, second_id = sorted((datapoint_a_id, datapoint_b_id))
    parameters = (
        first_id,
        second_id,
        assessment.divergence_bps,
        assessment.tolerance_bps_at_write,
        assessment.status,
    )

    with connection.transaction():
        row = connection.execute(
            """
            insert into corroborations (
              datapoint_a_id, datapoint_b_id, divergence_bps,
              tolerance_bps_at_write, status
            ) values (%s, %s, %s, %s, %s)
            on conflict (datapoint_a_id, datapoint_b_id) do nothing
            returning id, datapoint_a_id, datapoint_b_id, divergence_bps,
                      tolerance_bps_at_write, status
            """,
            parameters,
        ).fetchone()
        if row is None:
            row = connection.execute(
                """
                select id, datapoint_a_id, datapoint_b_id, divergence_bps,
                       tolerance_bps_at_write, status
                from corroborations
                where datapoint_a_id = %s and datapoint_b_id = %s
                """,
                (first_id, second_id),
            ).fetchone()

    if row is None:
        raise RuntimeError("database did not return the corroboration record")
    return CorroborationRecord(
        id=cast(int, row[0]),
        datapoint_a_id=cast(int, row[1]),
        datapoint_b_id=cast(int, row[2]),
        divergence_bps=cast(float, row[3]),
        tolerance_bps_at_write=cast(float, row[4]),
        status=cast(CorroborationStatus, row[5]),
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


def run_live_corroboration(
    connection: psycopg.Connection[tuple[object, ...]],
) -> CorroborationRecord | TimestampMismatch:
    """Fetch, persist, and compare the registered close at both live venues."""

    definition = next(
        entry for entry in load_registry().root if entry.key == okx.INDICATOR_KEY
    )
    corroboration = definition.corroboration
    if corroboration is None:
        raise ValueError(f"{definition.key} has no corroboration definition")

    source_a = okx.fetch_btc_daily_close()
    source_b = coinbase.fetch_btc_daily_close()
    if not isinstance(source_a, Ok) or not isinstance(source_b, Ok):
        raise TypeError(
            f"both live venues must return values: okx={source_a!r}, "
            f"coinbase={source_b!r}"
        )

    def persist_comparison() -> CorroborationRecord:
        source_a_id = persist_datapoint(
            connection,
            definition=definition,
            asset=definition.definable_for[0],
            measured_on=okx.MEASURED_ON,
            result=source_a,
        )
        source_b_definition = definition.model_copy(
            update={
                "vendor": corroboration.venue,
                "endpoint": coinbase.ENDPOINT,
            }
        )
        source_b_id = persist_datapoint(
            connection,
            definition=source_b_definition,
            asset=definition.definable_for[0],
            measured_on=coinbase.MEASURED_ON,
            result=source_b,
        )
        return record_corroboration(
            connection,
            definition=definition,
            datapoint_a_id=source_a_id,
            source_a_value=source_a.value,
            datapoint_b_id=source_b_id,
            source_b_value=source_b.value,
        )

    return gate_timestamp_comparison(
        source_a.source_timestamp,
        source_b.source_timestamp,
        compare=persist_comparison,
    )
