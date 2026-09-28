import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.fred import (
    FRED_BACKFILL_CHUNK_DAYS,
    FRED_BACKFILL_LIMIT,
    FRED_SERIES_OBSERVATIONS_ENDPOINT,
    BackfilledFredOk,
    FredOk,
    FredSeries,
    backfill_fred_initial_release,
    fetch_fred_series,
)
from ingest.registry import load_registry

ENV_FILE = Path(__file__).resolve().parents[1] / ".env.local"


def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, raw_value = line.partition("=")
            if separator and key.strip() == name and raw_value.strip():
                return raw_value.strip().strip("'\"")

    return None



def definition(key: str):
    return next(entry for entry in load_registry().root if entry.key == key)


def observation(
    *,
    realtime_start: str,
    observation_date: str,
    value: str,
) -> dict[str, str]:
    return {
        "realtime_start": realtime_start,
        "realtime_end": "9999-12-31",
        "date": observation_date,
        "value": value,
    }


def fred_payload(
    request: httpx.Request,
    observations: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "realtime_start": request.url.params["realtime_start"],
        "realtime_end": request.url.params["realtime_end"],
        "observation_start": "1776-07-04",
        "observation_end": "9999-12-31",
        "units": "lin",
        "output_type": 4,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": request.url.params["sort_order"],
        "count": len(observations),
        "offset": 0,
        "limit": int(request.url.params["limit"]),
        "observations": observations,
    }


def test_fred_registry_entries_are_wired_to_real_backfill_recipe() -> None:
    entries = {entry.key: entry for entry in load_registry().root}

    assert entries["macro_vixcls"].backfill_recipe == "fred_initial_release"
    assert entries["macro_dff"].backfill_recipe == "fred_initial_release"
    assert entries["macro_t10y2y"].backfill_recipe == "fred_initial_release"
    assert entries["macro_dfii10"].backfill_recipe == "fred_initial_release"
    assert entries["macro_dtwexbgs"].backfill_recipe == "fred_initial_release"
    assert entries["macro_cpiaucsl"].backfill_recipe == "fred_initial_release"
    assert entries["macro_m2sl"].backfill_recipe == "fred_initial_release"
    assert "fred_initial_release" in BACKFILL_RECIPES


@pytest.mark.parametrize("key,series_id", (("macro_m2sl", "M2SL"), ("macro_vixcls", "VIXCLS")))
def test_fred_backfill_requests_output_type_4_in_small_realtime_start_chunks(
    key: str,
    series_id: str,
) -> None:
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=fred_payload(request, []), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_fred_initial_release(
            definition(key),
            client=client,
            api_key="test-key",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 3, 15),
        )

    assert runs == ()
    assert len(requested) == 3
    for request in requested:
        assert str(request.url).startswith(FRED_SERIES_OBSERVATIONS_ENDPOINT)
        assert request.url.params["series_id"] == series_id
        assert request.url.params["output_type"] == "4"
        assert request.url.params["limit"] == str(FRED_BACKFILL_LIMIT)
        realtime_start = date.fromisoformat(request.url.params["realtime_start"])
        realtime_end = date.fromisoformat(request.url.params["realtime_end"])
        assert (realtime_end - realtime_start).days + 1 <= FRED_BACKFILL_CHUNK_DAYS


def test_backfilled_value_at_live_observation_date_matches_live_initial_release() -> None:
    row = observation(
        realtime_start="2026-09-11",
        observation_date="2026-08-01",
        value="323.976",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fred_payload(request, [row]), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        live = fetch_fred_series(
            FredSeries("CPIAUCSL", source_field=definition("macro_cpiaucsl").source_field),
            client=client,
            api_key="test-key",
        )
        backfilled_runs = backfill_fred_initial_release(
            definition("macro_cpiaucsl"),
            client=client,
            api_key="test-key",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

    assert isinstance(live, FredOk)
    assert len(backfilled_runs) == 1
    backfilled = backfilled_runs[0].indicators["macro_cpiaucsl"]
    assert isinstance(backfilled, BackfilledFredOk)
    assert backfilled.reference_period == live.reference_period
    assert backfilled.value == live.value
    assert backfilled.source_timestamp == live.source_timestamp
    assert backfilled.published_at == live.published_at


def test_revised_same_observation_date_backfills_with_live_revision_disclosure() -> None:
    rows = [
        observation(
            realtime_start="2026-09-11",
            observation_date="2026-08-01",
            value="323.976",
        ),
        observation(
            realtime_start="2026-09-18",
            observation_date="2026-08-01",
            value="324.001",
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fred_payload(request, rows), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_fred_initial_release(
            definition("macro_cpiaucsl"),
            client=client,
            api_key="test-key",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

    assert len(runs) == 2
    first = runs[0].indicators["macro_cpiaucsl"]
    second = runs[1].indicators["macro_cpiaucsl"]
    assert isinstance(first, BackfilledFredOk)
    assert isinstance(second, BackfilledFredOk)
    assert "revised from" not in first.source_field
    assert "revised from 323.976" in second.source_field
    assert second.reference_period == "2026-08-01"
    assert second.source_timestamp == datetime(2026, 9, 18, tzinfo=UTC)


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or _env_value("DATABASE_URL")
    if database_url:
        return database_url
    raise RuntimeError(
        "Live FRED backfill persistence tests require TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_backfill_fred_{uuid4().hex}"
    connection = psycopg.connect(_database_url(), autocommit=True)

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
            schema_name = sql.Identifier(schema).as_string(connection)
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                migration_sql = migration.read_text(encoding="utf-8").replace(
                    "public.", f"{schema_name}."
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
def test_live_dff_run_backfill_persists_multi_year_span_without_vintage_cap(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    # A window spanning more than one FRED_BACKFILL_CHUNK_DAYS=365 chunk is required to
    # actually exercise chunking - a 90-120 day window fits in a single chunk and would
    # pass identically whether or not chunking worked at all. Kept just over 2 chunks
    # (not 3+) so persisting real rows for a daily series stays fast enough to run
    # reliably in CI.
    end = datetime.now(UTC).date()
    start = end - timedelta(days=380 * 2)

    def recent_live_dff_recipe(recipe_entry):
        assert recipe_entry.key == "macro_dff"
        return backfill_fred_initial_release(
            recipe_entry,
            start_date=start,
            end_date=end,
        )

    row_ids = run_backfill(
        postgres,
        indicator_key="macro_dff",
        recipes={**BACKFILL_RECIPES, "fred_initial_release": recent_live_dff_recipe},
    )

    assert row_ids
    persisted = postgres.execute(
        """
        select value, source_timestamp, reference_period, endpoint, origin
        from datapoints
        where id = any(%s)
        order by source_timestamp asc
        """,
        (list(row_ids),),
    ).fetchall()
    assert persisted
    assert all(row[4] == "backfill" for row in persisted)
    assert all("output_type=4" in row[3] for row in persisted)

    reference_dates = [date.fromisoformat(row[2]) for row in persisted]
    span_days = (max(reference_dates) - min(reference_dates)).days
    assert span_days > 365, (
        f"backfilled span was only {span_days} days - chunking across "
        "FRED_BACKFILL_CHUNK_DAYS boundaries was not actually exercised"
    )

    # The endpoints used must span more than one distinct realtime_start/end chunk -
    # otherwise this test could pass even if chunking silently stopped working.
    distinct_chunks = {row[3] for row in persisted}
    assert len(distinct_chunks) >= 2, (
        f"only {len(distinct_chunks)} distinct chunk endpoint(s) were used for a "
        f"{span_days}-day span - chunking is not actually happening"
    )

    # Cross-check the newest persisted value against a fresh, independent live call to
    # FRED's default (non-chunked) query for the same observation date.
    newest = persisted[-1]
    fresh = fetch_fred_series(FredSeries(series_id="DFF"))
    assert isinstance(fresh, FredOk)
    if fresh.reference_period == newest[2]:
        assert fresh.value == pytest.approx(float(newest[0]), rel=1e-9, abs=0.0)
