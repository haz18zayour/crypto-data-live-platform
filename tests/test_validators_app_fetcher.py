import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.validators_app import (
    VALIDATORS_APP_EPOCHS_ENDPOINT,
    fetch_sol_staking,
)
from ingest.schemas import ValidatorsAppEpochsResponse
from ingest.status import Error, Ok, Reason

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)


def epochs_payload(source_timestamp: datetime) -> dict[str, object]:
    return {
        "epochs": [
            {
                "epoch": 472,
                "starting_slot": 203904008,
                "slots_in_epoch": 432000,
                "network": "mainnet",
                "created_at": source_timestamp.isoformat().replace("+00:00", "Z"),
                "total_rewards": 181321548661377,
                "total_active_stake": 390383623782551636,
            }
        ],
        "epochs_count": 169,
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
            json=epochs_payload(NOW - timedelta(days=1)),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.value == 390383623.78255165
    request = requested[0]
    assert str(request.url).startswith(VALIDATORS_APP_EPOCHS_ENDPOINT)
    assert request.url.params["per"] == "1"
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
    payload = epochs_payload(NOW - timedelta(days=1))
    payload["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ValidatorsAppEpochsResponse.model_validate(payload)

    renamed = epochs_payload(NOW - timedelta(days=1))
    epochs = renamed["epochs"]
    assert isinstance(epochs, list)
    epochs[0]["active_stake"] = epochs[0].pop("total_active_stake")
    with pytest.raises(ValidationError, match="total_active_stake"):
        ValidatorsAppEpochsResponse.model_validate(renamed)

    retyped = epochs_payload(NOW - timedelta(days=1))
    epochs = retyped["epochs"]
    assert isinstance(epochs, list)
    epochs[0]["total_active_stake"] = "390383623782551636"
    with pytest.raises(ValidationError, match="int_type"):
        ValidatorsAppEpochsResponse.model_validate(retyped)


def test_malformed_response_becomes_fetch_failed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", "configured-token")
    payload = epochs_payload(NOW - timedelta(days=1))
    payload["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


def test_source_timestamp_is_epoch_created_at_and_must_be_strictly_past(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALIDATORS_APP_API_TOKEN", "configured-token")
    source_timestamp = NOW - timedelta(days=1)

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=epochs_payload(source_timestamp),
                request=request,
            )
        )
    ) as client:
        result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(result, Ok)
    assert result.source_timestamp == source_timestamp
    assert result.source_timestamp < NOW

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=epochs_payload(NOW),
                request=request,
            )
        )
    ) as client:
        future_result = fetch_sol_staking(client=client, now=NOW)

    assert isinstance(future_result, Error)
    assert future_result.reason is Reason.FETCH_FAILED
    assert "future" in future_result.detail.lower()


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
