import os
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from ingest.backfill import BACKFILL_RECIPES, run_backfill
from ingest.fetchers.sosovalue import (
    BACKFILL_LIMIT,
    SOSOVALUE_SUMMARY_HISTORY_ENDPOINT,
    SosoValueEtfFlowOk,
    backfill_sosovalue_etf_flows,
    fetch_etf_net_flow,
    probe_sosovalue_summary_history,
)
from ingest.registry import load_registry
from ingest.status import Error, Reason

MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
ENV_FILE = MIGRATIONS.parents[1] / ".env.local"


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


def _required_env_value(name: str) -> str:
    value = _env_value(name)
    if value:
        return value
    raise RuntimeError(f"{name} is required for the live SoSoValue backfill probe")


def _database_url() -> str:
    database_url = _env_value("TEST_DATABASE_URL") or _env_value("DATABASE_URL")
    if database_url:
        return database_url
    raise RuntimeError(
        "Live SoSoValue backfill persistence tests require TEST_DATABASE_URL, "
        "DATABASE_URL, or DATABASE_URL in .env.local"
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    schema = f"test_backfill_sosovalue_{uuid4().hex}"
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


def _payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"code": 0, "message": "success", "data": rows, "details": None}


def _row(date: str, flow: float) -> dict[str, object]:
    return {
        "date": date,
        "total_net_inflow": flow,
        "total_value_traded": 13534833596.095,
        "total_net_assets": 152000000000.0,
        "cum_net_inflow": 44000000000.0,
    }


def test_sosovalue_registry_entry_is_wired_to_real_backfill_recipe() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "spot_etf_net_flow")

    assert entry.backfill_recipe == "sosovalue_etf_flows"
    assert BACKFILL_RECIPES[entry.backfill_recipe] is backfill_sosovalue_etf_flows


def test_sosovalue_backfill_persists_decimal_values_via_str_conversion() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=_payload([_row("2026-09-25", 190646110.255)]),
            request=request,
        )

    entry = next(entry for entry in load_registry().root if entry.key == "spot_etf_net_flow")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runs = backfill_sosovalue_etf_flows(entry, client=client, api_key="test-key")

    values = [
        next(iter(run.indicators.values()))
        for run in runs
        if next(iter(run.indicators.keys())).endswith("\x1fBTC")
    ]
    assert isinstance(values[0], SosoValueEtfFlowOk)
    assert values[0].value == Decimal("190646110.255")
    assert values[0].value != Decimal.from_float(190646110.255)
    assert values[0].source_timestamp == datetime(2026, 9, 25, tzinfo=UTC)
    assert requests[0].url.params["limit"] == str(BACKFILL_LIMIT)


def test_sosovalue_probe_records_shape_date_range_and_measured_rate_limit() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 4:
            return httpx.Response(429, json={"code": 42901}, request=request)
        return httpx.Response(
            200,
            json=_payload(
                [
                    _row("2024-01-02", 0.1),
                    _row("2026-09-25", -55066297.155),
                ]
            ),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        probe = probe_sosovalue_summary_history(
            "BTC",
            client=client,
            api_key="test-key",
            rate_probe_requests=5,
        )

    assert probe.oldest_date == "2024-01-02"
    assert probe.newest_date == "2026-09-25"
    assert "total_net_inflow" in probe.fields
    assert probe.rate_limit_status == 429
    assert "request 3" in probe.rate_limit_detail


def test_bnb_etf_flow_remains_not_definable_and_not_backfilled() -> None:
    requested_symbols: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_symbols.append(request.url.params["symbol"])
        return httpx.Response(
            200,
            json=_payload([_row("2026-09-25", 0.1)]),
            request=request,
        )

    entry = next(entry for entry in load_registry().root if entry.key == "spot_etf_net_flow")
    assert entry.not_definable is not None
    assert entry.not_definable.reason_for("BNB")
    assert "BNB" not in entry.definable_for
    result = fetch_etf_net_flow("BNB", api_key="test-key")
    assert isinstance(result, Error)
    assert result.reason is Reason.NOT_DEFINABLE

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backfill_sosovalue_etf_flows(entry, client=client, api_key="test-key")

    assert requested_symbols == ["BTC", "ETH", "SOL"]


@pytest.mark.integration
def test_live_sosovalue_run_backfill_persists_real_vendor_rows_after_probe(
    postgres: psycopg.Connection[tuple[object, ...]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = _required_env_value("SOSOVALUE_API_KEY")
    probe = probe_sosovalue_summary_history(
        "BTC",
        api_key=api_key,
        sample_limit=BACKFILL_LIMIT,
        rate_probe_requests=0,
    )
    assert probe.rows == BACKFILL_LIMIT
    assert probe.oldest_date < probe.newest_date
    assert probe.rate_limit_status in {200, 429}

    monkeypatch.setenv("SOSOVALUE_API_KEY", api_key)
    row_ids = run_backfill(postgres, indicator_key="spot_etf_net_flow")

    assert row_ids
    persisted = postgres.execute(
        """
        select asset, value, source_timestamp, reference_period, endpoint,
               source_field, origin
        from datapoints
        where id = any(%s)
        order by asset, source_timestamp
        """,
        (list(row_ids),),
    ).fetchall()
    assert persisted
    assert {row[0] for row in persisted} == {"BTC", "ETH", "SOL"}
    assert all(row[6] == "backfill" for row in persisted)
    assert all(str(row[4]).startswith(SOSOVALUE_SUMMARY_HISTORY_ENDPOINT) for row in persisted)
    assert all(f"backfill limit={BACKFILL_LIMIT}" in str(row[5]) for row in persisted)
    assert any(row[0] == "BTC" and row[3] == probe.oldest_date for row in persisted)


@pytest.mark.integration
def test_live_sosovalue_history_probe_confirms_real_shape_range_and_rate_limit() -> None:
    probe = probe_sosovalue_summary_history(
        "BTC",
        api_key=_required_env_value("SOSOVALUE_API_KEY"),
        rate_probe_requests=25,
    )

    assert probe.rows > 1
    assert probe.oldest_date < probe.newest_date
    assert "total_net_inflow" in probe.fields
    assert probe.rate_limit_status in {200, 429}
    assert probe.rate_limit_detail
