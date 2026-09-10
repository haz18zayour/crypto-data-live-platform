"""Write typed ingestion results with complete registry provenance."""

from datetime import UTC, datetime
from typing import cast

import psycopg

from ingest.registry import IndicatorDefinition
from ingest.status import Ok, Result, Stale


def _utc_now() -> datetime:
    return datetime.now(UTC)


def persist_datapoint(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    definition: IndicatorDefinition,
    asset: str,
    measured_on: str,
    result: Result,
) -> int:
    """Persist one result and return its row id."""

    if measured_on != asset:
        raise ValueError("measured_on must equal asset")

    fetched_at = _utc_now()
    if isinstance(result, (Ok, Stale)):
        value = result.value
        reason = None
        source_timestamp = result.source_timestamp
        if source_timestamp.tzinfo is None or source_timestamp.utcoffset() is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if source_timestamp > fetched_at:
            raise ValueError("source_timestamp cannot be in the future")
    else:
        value = None
        reason = result.reason.value
        source_timestamp = None

    identity = (
        f"{definition.key}\x1f{asset}\x1f{definition.vendor}\x1f"
        f"{source_timestamp.isoformat() if source_timestamp else '<NULL>'}"
    )
    values = (
        measured_on,
        value,
        result.status,
        reason,
        definition.vendor,
        definition.endpoint,
        definition.source_field,
        fetched_at,
        source_timestamp,
    )

    with connection.transaction():
        connection.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))", (identity,)
        )
        existing = connection.execute(
            """
            select id
            from datapoints
            where indicator_key = %s
              and asset = %s
              and source_vendor = %s
              and source_timestamp is not distinct from %s
            for update
            """,
            (definition.key, asset, definition.vendor, source_timestamp),
        ).fetchone()

        if existing is None:
            row = connection.execute(
                """
                insert into datapoints (
                  indicator_key, asset, measured_on, value, status, reason,
                  source_vendor, endpoint, source_field, fetched_at, source_timestamp
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                returning id
                """,
                (definition.key, asset, *values),
            ).fetchone()
        else:
            row = connection.execute(
                """
                update datapoints
                set measured_on = %s,
                    value = %s,
                    status = %s,
                    reason = %s,
                    source_vendor = %s,
                    endpoint = %s,
                    source_field = %s,
                    fetched_at = %s,
                    source_timestamp = %s
                where id = %s
                returning id
                """,
                (*values, existing[0]),
            ).fetchone()

    if row is None:
        raise RuntimeError("database did not return the persisted datapoint id")
    return cast(int, row[0])
