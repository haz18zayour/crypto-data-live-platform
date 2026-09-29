from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from ingest import canary
from ingest.registry import IndicatorDefinition, IndicatorRegistry, load_registry
from ingest.schemas import OkxCandleResponse

HEARTBEAT_URL = "https://hc-ping.com/canary-check-id"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env.local"


def definition(key: str, vendor: str, endpoint: str) -> IndicatorDefinition:
    return IndicatorDefinition.model_validate(
        {
            "key": key,
            "vendor": vendor,
            "endpoint": endpoint,
            "source_field": "data[0][4]",
            "definable_for": ["BTC"],
            "required_bars": 1,
            "frozen_after_observations": 3,
            "expected_update_interval_seconds": 86_400,
            "freshness_warn_seconds": 108_000,
            "freshness_stale_seconds": 172_800,
        }
    )


def valid_payload() -> dict[str, object]:
    return {
        "code": "0",
        "msg": "",
        "data": [["1", "2", "3", "4", "5", "6", "7", "8", "1"]],
    }


def install_registry(
    monkeypatch: pytest.MonkeyPatch,
    *definitions: IndicatorDefinition,
) -> None:
    registry = IndicatorRegistry.model_validate(definitions)
    monkeypatch.setattr(canary, "load_registry", lambda: registry)


def heartbeat_client(requested_urls: list[str]) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                requested_urls.append(str(request.url))
                or httpx.Response(200, request=request)
            )
        )
    )


def test_canary_validates_every_endpoint_loaded_from_the_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoints = (
        "https://one.example.test/candles",
        "https://new.example.test/candles",
    )
    install_registry(
        monkeypatch,
        definition("one", "okx", endpoints[0]),
        definition("new", "new-vendor", endpoints[1]),
    )
    monkeypatch.setattr(
        canary,
        "RESPONSE_MODELS",
        {"one": OkxCandleResponse, "new": OkxCandleResponse},
    )
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json=valid_payload(), request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        heartbeat_client(requested_urls) as healthchecks,
    ):
        results = canary.run_canary(
            HEARTBEAT_URL,
            client=client,
            heartbeat_client=healthchecks,
        )

    assert requested_urls == [*endpoints, HEARTBEAT_URL]
    assert [(result.vendor, result.endpoint, result.status) for result in results] == [
        ("okx", endpoints[0], "OK"),
        ("new-vendor", endpoints[1], "OK"),
    ]


def _database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if database_url:
        return database_url

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL" and value.strip():
                return value.strip().strip("'\"")

    raise RuntimeError(
        "Canary database test requires TEST_DATABASE_URL, DATABASE_URL, "
        "or DATABASE_URL in .env.local"
    )


@pytest.fixture
def datapoint_count() -> Iterator[tuple[psycopg.Connection[tuple[object, ...]], str]]:
    schema = f"test_canary_{uuid4().hex}"
    try:
        connection = psycopg.connect(_database_url(), autocommit=True)
    except psycopg.OperationalError:
        raise RuntimeError(
            "Canary database test could not connect; check TEST_DATABASE_URL, "
            "DATABASE_URL, or DATABASE_URL in .env.local"
        ) from None
    with connection:
        connection.execute(
            sql.SQL("create schema {}").format(sql.Identifier(schema))
        )
        connection.execute(
            sql.SQL("create table {}.datapoints (id integer primary key)").format(
                sql.Identifier(schema)
            )
        )
        connection.execute(
            sql.SQL("insert into {}.datapoints (id) values (1)").format(
                sql.Identifier(schema)
            )
        )
        try:
            yield connection, schema
        finally:
            assert schema.startswith("test_canary_")
            connection.execute(
                sql.SQL("drop schema {} cascade").format(sql.Identifier(schema))
            )


@pytest.mark.integration
def test_canary_writes_no_datapoints(
    datapoint_count: tuple[psycopg.Connection[tuple[object, ...]], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection, schema = datapoint_count
    registered = definition(
        "btc_daily_close", "okx", "https://one.example.test/candles"
    )
    install_registry(monkeypatch, registered)
    monkeypatch.setenv(
        "DATABASE_URL",
        make_conninfo(_database_url(), options=f"-c search_path={schema}"),
    )
    count_query = sql.SQL("select count(*) from {}.datapoints").format(
        sql.Identifier(schema)
    )
    before = connection.execute(count_query).fetchone()
    assert before is not None

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=valid_payload(), request=request)
    )
    with (
        httpx.Client(transport=transport) as client,
        httpx.Client(transport=transport) as healthchecks,
    ):
        canary.run_canary(
            HEARTBEAT_URL,
            client=client,
            heartbeat_client=healthchecks,
        )

    after = connection.execute(count_query).fetchone()
    assert after == before == (1,)


def test_shape_mismatch_fails_and_names_the_vendor_and_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered = definition(
        "btc_daily_close", "okx", "https://one.example.test/candles"
    )
    install_registry(monkeypatch, registered)
    malformed = valid_payload()
    malformed["data"] = [["1", "2", "3", "4", "5", "6", "7", "8"]]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=malformed, request=request)
    )

    with (
        httpx.Client(transport=transport) as client,
        httpx.Client(transport=transport) as healthchecks,
        pytest.raises(canary.CanaryFailure, match=r"okx.*data\.0\.8") as raised,
    ):
        canary.run_canary(
            HEARTBEAT_URL,
            client=client,
            heartbeat_client=healthchecks,
        )

    assert raised.value.results[0].status == "ERROR"


def test_canary_pings_success_and_failure_heartbeat_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered = definition(
        "btc_daily_close", "okx", "https://one.example.test/candles"
    )
    install_registry(monkeypatch, registered)
    heartbeat_urls: list[str] = []

    with heartbeat_client(heartbeat_urls) as healthchecks:
        good_transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=valid_payload(), request=request
            )
        )
        with httpx.Client(transport=good_transport) as client:
            canary.run_canary(
                HEARTBEAT_URL,
                client=client,
                heartbeat_client=healthchecks,
            )

        bad_transport = httpx.MockTransport(
            lambda request: httpx.Response(503, request=request)
        )
        with (
            httpx.Client(transport=bad_transport) as client,
            pytest.raises(canary.CanaryFailure),
        ):
            canary.run_canary(
                HEARTBEAT_URL,
                client=client,
                heartbeat_client=healthchecks,
            )

    assert heartbeat_urls == [HEARTBEAT_URL, f"{HEARTBEAT_URL}/fail"]


def test_one_vendor_failure_does_not_prevent_later_vendors_being_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoints = (
        "https://broken.example.test/candles",
        "https://healthy.example.test/candles",
    )
    install_registry(
        monkeypatch,
        definition("broken", "broken-vendor", endpoints[0]),
        definition("healthy", "okx", endpoints[1]),
    )
    monkeypatch.setattr(
        canary,
        "RESPONSE_MODELS",
        {"broken": OkxCandleResponse, "healthy": OkxCandleResponse},
    )
    requested_endpoints: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_endpoints.append(str(request.url))
        payload = {"code": "0", "msg": "", "data": "reshaped"}
        if str(request.url) == endpoints[1]:
            payload = valid_payload()
        return httpx.Response(200, json=payload, request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        heartbeat_client([]) as healthchecks,
        pytest.raises(canary.CanaryFailure) as raised,
    ):
        canary.run_canary(
            HEARTBEAT_URL,
            client=client,
            heartbeat_client=healthchecks,
        )

    assert requested_endpoints == list(endpoints)
    assert [result.status for result in raised.value.results] == ["ERROR", "OK"]


@pytest.mark.integration
def test_canary_runs_against_live_vendors_and_reports_per_vendor_status(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heartbeat_calls: list[tuple[str, bool]] = []
    monkeypatch.setenv("HEALTHCHECK_URL_CONTRACT_CANARY", HEARTBEAT_URL)
    monkeypatch.setattr(
        canary,
        "_ping",
        lambda url, *, failed, client: heartbeat_calls.append((url, failed)),
    )

    exit_code = canary.main()

    registry = load_registry()
    report = json.loads(capsys.readouterr().out)
    assert {
        (result["vendor"], result["endpoint"]) for result in report
    } == {(entry.vendor, entry.endpoint) for entry in registry.root}
    for result in report:
        assert result["status"] in ("OK", "ERROR")
        if result["status"] == "ERROR":
            assert result["detail"]

    # This canary hits real, live third-party endpoints across five vendors — a single
    # vendor's transient hiccup is not a defect, it is exactly the condition this canary
    # exists to catch and report per-endpoint. A large fraction failing at once, however,
    # is a real regression, not vendor noise.
    failures = [result for result in report if result["status"] == "ERROR"]
    assert len(failures) / len(report) <= 0.1, (
        f"{len(failures)}/{len(report)} live endpoints failed shape-check: {failures}"
    )

    # The canary's own all-or-nothing alerting must stay consistent with what it found.
    any_failed = bool(failures)
    assert exit_code == (1 if any_failed else 0)
    assert heartbeat_calls == [(HEARTBEAT_URL, any_failed)]
