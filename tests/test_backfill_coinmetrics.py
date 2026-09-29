import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.coinmetrics import (
    BACKFILL_PAGE_SIZE,
    COINMETRICS_ASSET_METRICS_ENDPOINT,
    COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT,
    CoinMetricsRateLimiter,
    _catalog_metric_min_times,
    _history_rows,
    backfill_coinmetrics_asset_metrics,
)
from ingest.registry import load_registry

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)
MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


def definition(key: str):
    return next(entry for entry in load_registry().root if entry.key == key)


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
        "Live Coin Metrics backfill persistence test requires TEST_DATABASE_URL, "
        "DATABASE_URL, or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_backfill_coinmetrics_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "Live Coin Metrics backfill persistence test could not connect; check "
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


def catalog_payload(
    asset: str,
    metric_min_times: dict[str, datetime],
) -> dict[str, list[dict[str, object]]]:
    return {
        "data": [
            {
                "asset": asset.casefold(),
                "metrics": [
                    {
                        "metric": metric,
                        "frequencies": [
                            {
                                "frequency": "1d",
                                "min_time": min_time.isoformat().replace(
                                    "+00:00", "Z"
                                ),
                            }
                        ],
                    }
                    for metric, min_time in metric_min_times.items()
                ],
            }
        ]
    }


def row(
    timestamp: datetime,
    *,
    asset: str = "btc",
    metric: str = "CapMVRVCur",
    value: str = "2.5",
) -> dict[str, str]:
    return {
        "asset": asset.casefold(),
        "time": timestamp.isoformat().replace("+00:00", "Z"),
        metric: value,
    }


def test_coinmetrics_registry_entries_are_wired_to_real_backfill_recipe() -> None:
    entries = {entry.key: entry for entry in load_registry().root}

    assert entries["btc_mvrv"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["btc_active_addresses"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["btc_exchange_flow"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["eth_mvrv"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["eth_active_addresses"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["eth_exchange_flow"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["bnb_mvrv"].backfill_recipe == "coinmetrics_asset_metrics"
    assert entries["bnb_active_addresses"].backfill_recipe == "coinmetrics_asset_metrics"
    assert "coinmetrics_asset_metrics" in BACKFILL_RECIPES


def test_backfill_queries_catalog_min_time_before_requesting_history() -> None:
    flow_in_min = datetime(2020, 1, 1, tzinfo=UTC)
    flow_out_min = datetime(2020, 2, 1, tzinfo=UTC)
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        if str(request.url).startswith(COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT):
            assert len(requested) == 1
            assert request.url.params["assets"] == "btc"
            assert request.url.params["metrics"] == "FlowInExNtv,FlowOutExNtv"
            return httpx.Response(
                200,
                json=catalog_payload(
                    "btc",
                    {
                        "FlowInExNtv": flow_in_min,
                        "FlowOutExNtv": flow_out_min,
                    },
                ),
                request=request,
            )
        assert len(requested) == 2
        assert request.url.params["start_time"] == flow_out_min.isoformat().replace(
            "+00:00", "Z"
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "asset": "btc",
                        "time": flow_out_min.isoformat().replace("+00:00", "Z"),
                        "FlowInExNtv": "125.5",
                        "FlowOutExNtv": "100.25",
                    }
                ]
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_coinmetrics_asset_metrics(
            definition("btc_exchange_flow"),
            client=client,
        )

    assert len(runs) == 1
    result = runs[0].indicators["btc_exchange_flow"]
    assert result.value == 25.25
    assert result.source_timestamp == flow_out_min
    assert "FlowInExNtv=2020-01-01T00:00:00+00:00" in result.source_field
    assert "FlowOutExNtv=2020-02-01T00:00:00+00:00" in result.source_field


def test_empty_response_inside_entitlement_window_is_genuine_empty_history() -> None:
    min_time = datetime(2021, 1, 1, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT):
            return httpx.Response(
                200,
                json=catalog_payload("btc", {"CapMVRVCur": min_time}),
                request=request,
            )
        assert request.url.params["start_time"] == min_time.isoformat().replace(
            "+00:00", "Z"
        )
        return httpx.Response(200, json={"data": []}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_coinmetrics_asset_metrics(definition("btc_mvrv"), client=client)

    assert runs == ()


def test_start_time_outside_entitlement_window_is_rejected_before_history_request() -> None:
    requested: list[httpx.Request] = []
    min_time = datetime(2021, 1, 1, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        if str(request.url).startswith(COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT):
            return httpx.Response(
                200,
                json=catalog_payload("btc", {"CapMVRVCur": min_time}),
                request=request,
            )
        raise AssertionError("history should not be requested before min_time")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        catalog_min_times = _catalog_metric_min_times(
            "BTC",
            ("CapMVRVCur",),
            client=client,
        )
        with pytest.raises(ValueError, match="precedes catalog-v2"):
            _history_rows(
                "BTC",
                ("CapMVRVCur",),
                start_time=min_time - timedelta(days=1),
                catalog_min_times=catalog_min_times,
                client=client,
            )

    assert len(requested) == 1


def test_coinmetrics_backfill_rate_limits_catalog_and_history_requests() -> None:
    fake_time = 100.0
    request_times: list[float] = []
    page_count = 0

    def clock() -> float:
        return fake_time

    def sleeper(seconds: float) -> None:
        nonlocal fake_time
        fake_time += seconds

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page_count
        request_times.append(fake_time)
        if str(request.url).startswith(COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT):
            return httpx.Response(
                200,
                json=catalog_payload("btc", {"CapMVRVCur": NOW}),
                request=request,
            )
        page_count += 1
        next_url = (
            f"{COINMETRICS_ASSET_METRICS_ENDPOINT}?page={page_count + 1}"
            if page_count < 11
            else None
        )
        return httpx.Response(
            200,
            json={
                "data": [
                    row(
                        NOW + timedelta(days=page_count),
                        value=str(1 + page_count),
                    )
                ],
                "next_page_url": next_url,
            },
            request=request,
        )

    limiter = CoinMetricsRateLimiter(clock=clock, sleeper=sleeper)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backfill_coinmetrics_asset_metrics(
            definition("btc_mvrv"),
            client=client,
            rate_limiter=limiter,
        )

    assert len(request_times) == 12
    for start in range(len(request_times) - 9):
        assert request_times[start + 9] - request_times[start] >= 6.0


def test_pagination_next_page_url_is_followed_unmodified_without_losing_rows() -> None:
    min_time = datetime(2020, 1, 1, tzinfo=UTC)
    next_page_url = (
        f"{COINMETRICS_ASSET_METRICS_ENDPOINT}?next_page_token=abc&kept=true"
    )
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url).startswith(COINMETRICS_CATALOG_V2_ASSET_METRICS_ENDPOINT):
            return httpx.Response(
                200,
                json=catalog_payload("btc", {"CapMVRVCur": min_time}),
                request=request,
            )
        if len(requested_urls) == 2:
            assert request.url.params["page_size"] == str(BACKFILL_PAGE_SIZE)
            return httpx.Response(
                200,
                json={
                    "data": [row(min_time, value="1.0")],
                    "next_page_url": next_page_url,
                },
                request=request,
            )
        assert requested_urls[-1] == next_page_url
        return httpx.Response(
            200,
            json={"data": [row(min_time + timedelta(days=1), value="2.0")]},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_coinmetrics_asset_metrics(definition("btc_mvrv"), client=client)

    assert [run.indicators["btc_mvrv"].value for run in runs] == [1.0, 2.0]
    assert [
        run.indicators["btc_mvrv"].source_timestamp for run in runs
    ] == [min_time, min_time + timedelta(days=1)]


def test_live_coinmetrics_run_backfill_persists_earliest_btc_active_addresses_at_catalog_min_time(
    postgres: psycopg.Connection[tuple[object, ...]],
) -> None:
    entry = definition("btc_active_addresses")
    catalog_min_times = _catalog_metric_min_times("BTC", ("AdrActCnt",))

    live_runs = ()

    def earliest_live_recipe(recipe_entry):
        nonlocal live_runs
        assert recipe_entry.key == entry.key
        live_runs = backfill_coinmetrics_asset_metrics(recipe_entry)
        assert live_runs
        return (
            min(
                live_runs,
                key=lambda run: run.indicators[
                    "btc_active_addresses"
                ].source_timestamp,
            ),
        )

    row_ids = run_backfill(
        postgres,
        indicator_key="btc_active_addresses",
        recipes={
            **BACKFILL_RECIPES,
            "coinmetrics_asset_metrics": earliest_live_recipe,
        },
    )

    assert row_ids
    assert live_runs
    earliest_run = min(
        live_runs,
        key=lambda run: run.indicators["btc_active_addresses"].source_timestamp,
    )
    earliest_result = earliest_run.indicators["btc_active_addresses"]
    persisted = postgres.execute(
        """
        select value, source_timestamp, endpoint, source_field, origin
        from datapoints
        where id = any(%s)
        """,
        (list(row_ids),),
    ).fetchone()
    assert persisted is not None
    value, source_timestamp, endpoint, source_field, origin = persisted
    assert float(value) == earliest_result.value
    assert source_timestamp == catalog_min_times["AdrActCnt"]
    assert source_timestamp == earliest_result.source_timestamp
    assert COINMETRICS_ASSET_METRICS_ENDPOINT in endpoint
    assert "catalog-v2 min_time AdrActCnt=" in source_field
    assert origin == "backfill"
