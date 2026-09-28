import os
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from ingest.backfill import BACKFILL_RECIPES
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


@pytest.mark.integration
def test_live_dff_chunked_backfill_spans_at_least_90_days_without_vintage_cap() -> None:
    if not os.environ.get("FRED_API_KEY"):
        pytest.skip("FRED_API_KEY is required for the live FRED backfill probe")

    end = datetime.now(UTC).date()
    runs = backfill_fred_initial_release(
        definition("macro_dff"),
        start_date=end - timedelta(days=120),
        end_date=end,
    )

    values = [
        run.indicators["macro_dff"]
        for run in runs
        if isinstance(run.indicators["macro_dff"], BackfilledFredOk)
    ]
    assert values
    reference_dates = [date.fromisoformat(value.reference_period) for value in values]
    assert (max(reference_dates) - min(reference_dates)).days >= 90
    assert all("output_type=4" in value.endpoint for value in values)
