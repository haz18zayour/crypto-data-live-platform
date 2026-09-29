from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from ingest.corroborate import (
    CorroborationRecord,
    assess_divergence,
    compute_divergence_bps,
    record_corroboration,
    run_live_corroboration,
)
from ingest.registry import IndicatorDefinition, load_registry

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


def _values_with_divergence(divergence_bps: float) -> tuple[float, float]:
    half_difference = divergence_bps / 200.0
    return 100.0 - half_difference, 100.0 + half_difference


def _definition(tolerance_bps: float) -> IndicatorDefinition:
    return IndicatorDefinition.model_validate(
        {
            "key": "btc_daily_close",
            "vendor": "okx",
            "endpoint": "https://www.okx.com/candles",
            "source_field": "close",
            "definable_for": ["BTC"],
            "required_bars": 1,
            "frozen_after_observations": 3,
            "expected_update_interval_seconds": 86_400,
            "freshness_warn_seconds": 108_000,
            "freshness_stale_seconds": 172_800,
            "corroboration": {
                "venue": "coinbase",
                "pair": "BTC-USD",
                "tolerance_bps": tolerance_bps,
            },
        }
    )


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class RecordingConnection:
    def __init__(self) -> None:
        self.stored: tuple[object, ...] | None = None

    def transaction(self) -> Any:
        return nullcontext()

    def execute(
        self, statement: str, parameters: tuple[object, ...]
    ) -> _Cursor:
        if "insert into corroborations" in statement:
            if self.stored is not None:
                return _Cursor(None)
            self.stored = (73, *parameters)
            return _Cursor(self.stored)
        if "select id, datapoint_a_id" in statement:
            return _Cursor(self.stored)
        raise AssertionError(f"unexpected SQL: {statement}")


def test_divergence_is_computed_in_basis_points_against_the_midpoint() -> None:
    forward = compute_divergence_bps(100.0, 101.0)
    reverse = compute_divergence_bps(101.0, 100.0)

    assert forward == pytest.approx(1.0 / 100.5 * 10_000)
    assert reverse == forward
    assert forward != pytest.approx(1.0 / 100.0 * 10_000)
    assert forward != pytest.approx(1.0 / 101.0 * 10_000)


def test_tolerance_is_read_per_indicator_from_the_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """\
- key: strict_close
  vendor: okx
  endpoint: https://okx.example.test/candles
  source_field: close
  definable_for: [BTC]
  required_bars: 1
  frozen_after_observations: 3
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  corroboration:
    venue: coinbase
    pair: BTC-USD
    tolerance_bps: 25
- key: loose_close
  vendor: okx
  endpoint: https://okx.example.test/candles
  source_field: close
  definable_for: [BTC]
  required_bars: 1
  frozen_after_observations: 3
  expected_update_interval_seconds: 86400
  freshness_warn_seconds: 108000
  freshness_stale_seconds: 172800
  corroboration:
    venue: coinbase
    pair: BTC-USD
    tolerance_bps: 40
""",
        encoding="utf-8",
    )
    strict, loose = load_registry(registry_path).root
    source_a, source_b = _values_with_divergence(35.2)

    assert assess_divergence(strict, source_a, source_b).status == "DIVERGED"
    assert assess_divergence(loose, source_a, source_b).status == "CORROBORATED"


def test_tolerance_in_force_at_write_time_cannot_be_retroactively_changed() -> (
    None
):
    connection = RecordingConnection()
    source_a, source_b = _values_with_divergence(35.2)

    original = record_corroboration(
        connection,  # type: ignore[arg-type]
        definition=_definition(25.0),
        datapoint_a_id=20,
        source_a_value=source_a,
        datapoint_b_id=10,
        source_b_value=source_b,
    )
    after_registry_edit = record_corroboration(
        connection,  # type: ignore[arg-type]
        definition=_definition(40.0),
        datapoint_a_id=20,
        source_a_value=source_a,
        datapoint_b_id=10,
        source_b_value=source_b,
    )

    assert original.tolerance_bps_at_write == 25.0
    assert original.status == "DIVERGED"
    assert after_registry_edit == original


def test_divergence_inside_tolerance_is_recorded_with_its_number() -> None:
    connection = RecordingConnection()
    source_a, source_b = _values_with_divergence(13.8)

    stored = record_corroboration(
        connection,  # type: ignore[arg-type]
        definition=_definition(25.0),
        datapoint_a_id=1,
        source_a_value=source_a,
        datapoint_b_id=2,
        source_b_value=source_b,
    )

    assert stored.status == "CORROBORATED"
    assert stored.divergence_bps == pytest.approx(13.8)
    assert stored.tolerance_bps_at_write == 25.0
    assert connection.stored is not None


def test_corroboration_never_produces_a_combined_venue_value() -> None:
    source_a, source_b = 78_834.1, 79_111.8

    assessment = assess_divergence(_definition(25.0), source_a, source_b)

    assert source_a == 78_834.1
    assert source_b == 79_111.8
    assert set(assessment.__dataclass_fields__) == {
        "divergence_bps",
        "tolerance_bps_at_write",
        "status",
    }
    assert not hasattr(assessment, "value")


@pytest.mark.parametrize(
    ("divergence_bps", "expected_status"),
    ((35.2, "DIVERGED"), (13.8, "CORROBORATED")),
)
def test_measured_defect_is_flagged_and_worst_honest_case_is_not(
    divergence_bps: float,
    expected_status: str,
) -> None:
    source_a, source_b = _values_with_divergence(divergence_bps)

    result = assess_divergence(_definition(25.0), source_a, source_b)

    assert result.divergence_bps == pytest.approx(divergence_bps)
    assert result.status == expected_status


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip("'\"")

    raise RuntimeError(
        "Live divergence test requires TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_divergence_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "Live divergence test could not connect to PostgreSQL; check "
            "TEST_DATABASE_URL, DATABASE_URL, or DATABASE_URL in .env.local"
        ) from None

    with connection:
        with connection.transaction():
            connection.execute(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                  END IF;
                  IF NOT EXISTS (
                    SELECT FROM pg_roles WHERE rolname = 'authenticated'
                  ) THEN
                    CREATE ROLE authenticated NOLOGIN;
                  END IF;
                END
                $$;
                """
            )
            connection.execute(
                sql.SQL("create schema {}").format(sql.Identifier(schema))
            )
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{sql.Identifier(schema).as_string(connection)}."
                )
                connection.execute(migration_sql)
        connection.execute(
            sql.SQL("set search_path to {}").format(sql.Identifier(schema))
        )

        try:
            yield connection
        finally:
            connection.execute(
                sql.SQL("drop schema if exists {} cascade").format(
                    sql.Identifier(schema)
                )
            )


@pytest.mark.integration
def test_real_run_against_both_live_venues_stores_divergence_and_tolerance(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    result = run_live_corroboration(postgres)

    assert isinstance(result, CorroborationRecord), result
    row = postgres.execute(
        """
        select c.divergence_bps, c.tolerance_bps_at_write, c.status,
               a.source_vendor, b.source_vendor, a.value, b.value
        from corroborations c
        join datapoints a on a.id = c.datapoint_a_id
        join datapoints b on b.id = c.datapoint_b_id
        where c.id = %s
        """,
        (result.id,),
    ).fetchone()

    assert row is not None
    assert row[:3] == (
        result.divergence_bps,
        25.0,
        result.status,
    )
    assert set(row[3:5]) == {"okx", "coinbase"}
    assert all(isinstance(value, float) for value in row[5:])
