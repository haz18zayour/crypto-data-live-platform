import os
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.validators_app import (
    VALIDATORS_APP_VALIDATORS_ENDPOINT,
    fetch_sol_staking,
)
from ingest.schemas import ValidatorsAppValidatorsResponse
from ingest.status import Error, Ok, Reason

NOW = datetime(2026, 9, 16, 12, tzinfo=UTC)


def validator_row(active_stake: int | None, *, network: str = "mainnet") -> dict[str, object]:
    return {
        "network": network,
        "account": "grptonHnt7YSmJokGK9TJJTBXDT8ca4LSWMHCCfzzPa",
        "active_stake": active_stake,
        "name": "gripto",
        "keybase_id": "",
        "www_url": "https://x.com/nl_gripto",
        "details": "enter the griptoverse for God's glory",
        "avatar_url": "https://example.test/avatar.jpg",
        "created_at": "2025-06-18 20:38:41 UTC",
        "updated_at": "2026-08-07 03:45:06 UTC",
        "admin_warning": None,
        "jito": True,
        "jito_commission": 0,
        "stake_pools_list": ["BlazeStake"],
        "is_active": True,
        "is_dz": True,
        "avatar_file_url": "https://example.test/avatar.jpg",
        "authorized_withdrawer_score": 0,
        "commission": 0,
        "data_center_concentration_score": 0,
        "delinquent": False,
        "published_information_score": 2,
        "root_distance_score": 2,
        "security_report_score": 1,
        "skipped_slot_score": 2,
        "skipped_after_score": 2,
        "software_version": "0.1106.40201",
        "software_version_score": 2,
        "stake_concentration_score": 0,
        "consensus_mods_score": 0,
        "vote_latency_score": 2,
        "total_score": 13,
        "vote_distance_score": 2,
        "software_client": "HarmonicFrankendancer",
        "software_client_id": 11,
        "ip": "70.40.184.229",
        "data_center_key": "395201-DE-Rodelheim",
        "autonomous_system_number": 395201,
        "latitude": "50.1234",
        "longitude": "8.6119",
        "data_center_host": None,
        "vote_account": "mnvkHm47ZmRKoSWuQZAfXLRiDPiKCq8PWkMWrp1Wwqe",
        "epoch_credits": 316464,
        "epoch": 1036,
        "skipped_slots": 0,
        "skipped_slot_percent": "0.0",
        "ping_time": None,
        "url": "https://www.validators.app/api/v1/validators/mainnet/grptonHnt7YSmJokGK9TJJTBXDT8ca4LSWMHCCfzzPa",
    }


def test_fetcher_authenticates_with_token_read_from_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", "  configured-token  ")
    requested: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(
            200,
            json=[validator_row(246811335149597), validator_row(611985566937719)],
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 858796.902087316
    request = requested[0]
    assert str(request.url).startswith(VALIDATORS_APP_VALIDATORS_ENDPOINT)
    assert request.headers["Token"] == "configured-token"
    assert "configured-token" not in str(request.url)


@pytest.mark.parametrize("configured_token", (None, "", "   "))
def test_missing_or_blank_token_returns_fetch_failed_without_request(
    monkeypatch: pytest.MonkeyPatch,
    configured_token: str | None,
) -> None:
    if configured_token is None:
        monkeypatch.delenv("VALIDATORS_APP_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", configured_token)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Validators.app should not be called without a token")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "VALIDATORS_APP_API_TOKEN" in result.detail


def test_http_429_returns_fetch_failed_with_status_and_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", "configured-token")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert requests == 1
    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    row = validator_row(246811335149597)
    row["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ValidatorsAppValidatorsResponse.model_validate([row])

    renamed = validator_row(246811335149597)
    renamed["stake"] = renamed.pop("active_stake")
    with pytest.raises(ValidationError, match="active_stake"):
        ValidatorsAppValidatorsResponse.model_validate([renamed])

    retyped = validator_row(246811335149597)
    retyped["active_stake"] = "246811335149597"
    with pytest.raises(ValidationError, match="int_type"):
        ValidatorsAppValidatorsResponse.model_validate([retyped])


def test_malformed_response_becomes_fetch_failed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", "configured-token")
    row = validator_row(246811335149597)
    row["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[row], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


def test_null_active_stake_on_some_validators_is_treated_as_zero_not_fatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[validator_row(None), validator_row(611985566937719)],
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        os.environ["VALIDATORS_APP_API_TOKEN"] = "configured-token"
        try:
            result = fetch_sol_staking(client=client, now=NOW)
        finally:
            del os.environ["VALIDATORS_APP_API_TOKEN"]

    assert isinstance(result, Ok)
    assert result.value == 611985.566937719


def test_all_null_active_stake_is_fetch_failed_not_a_zero_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[validator_row(None)], request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        os.environ["VALIDATORS_APP_API_TOKEN"] = "configured-token"
        try:
            result = fetch_sol_staking(client=client, now=NOW)
        finally:
            del os.environ["VALIDATORS_APP_API_TOKEN"]

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "zero" in result.detail.lower()


def test_non_mainnet_rows_are_excluded_from_the_sum() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                validator_row(611985566937719),
                validator_row(999_999_999, network="testnet"),
            ],
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        os.environ["VALIDATORS_APP_API_TOKEN"] = "configured-token"
        try:
            result = fetch_sol_staking(client=client, now=NOW)
        finally:
            del os.environ["VALIDATORS_APP_API_TOKEN"]

    assert isinstance(result, Ok)
    assert result.value == 611985.566937719


def test_source_timestamp_is_the_fetch_moment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[validator_row(611985566937719)], request=request
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        os.environ["VALIDATORS_APP_API_TOKEN"] = "configured-token"
        try:
            result = fetch_sol_staking(client=client, now=NOW)
        finally:
            del os.environ["VALIDATORS_APP_API_TOKEN"]

    assert isinstance(result, Ok)
    assert result.source_timestamp == NOW


@pytest.mark.integration
def test_live_validators_app_request_returns_real_sol_staking_data() -> None:
    if not os.environ.get("VALIDATORS_APP_API_TOKEN"):
        pytest.skip(
            "VALIDATORS_APP_API_TOKEN is required for the live Validators.app test"
        )

    result = fetch_sol_staking()

    assert isinstance(result, Ok), result
    assert result.source_timestamp < datetime.now(UTC)
    assert result.value > 0
