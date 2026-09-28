import os
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from ingest.backfill import BACKFILL_RECIPES
from ingest.fetchers.sosovalue import (
    BACKFILL_LIMIT,
    SosoValueEtfFlowOk,
    backfill_sosovalue_etf_flows,
    fetch_etf_net_flow,
    probe_sosovalue_summary_history,
)
from ingest.registry import load_registry
from ingest.status import Error, Reason


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
    assert values[0].value != Decimal(190646110.255)
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
def test_live_sosovalue_history_probe_confirms_real_shape_range_and_rate_limit() -> None:
    if not os.environ.get("SOSOVALUE_API_KEY"):
        pytest.skip("SOSOVALUE_API_KEY is required for the live SoSoValue probe")

    probe = probe_sosovalue_summary_history("BTC", rate_probe_requests=25)

    assert probe.rows > 1
    assert probe.oldest_date < probe.newest_date
    assert "total_net_inflow" in probe.fields
    assert probe.rate_limit_status in {200, 429}
    assert probe.rate_limit_detail
