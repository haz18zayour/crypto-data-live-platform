import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.alternative_me import (
    ALTERNATIVE_ME_FNG_ENDPOINT,
    AlternativeMeFearGreedOk,
    fetch_fear_greed_index,
)
from ingest.pipeline import run_all_assets
from ingest.registry import load_registry
from ingest.schemas import AlternativeMeFearGreedResponse
from ingest.status import Error, Reason

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "alternative_me_fng.json"


def fear_greed_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fetcher_parses_string_typed_value_into_numeric_ok_result() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=fear_greed_payload(), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fear_greed_index(client=client)

    assert isinstance(result, AlternativeMeFearGreedOk)
    assert result.value == 70
    assert isinstance(result.value, int)
    assert not isinstance(result.value, str)
    assert result.value_classification == "Greed"
    assert result.reference_period == "2026-09-28"
    assert result.source_timestamp == datetime(2026, 9, 28, tzinfo=UTC)
    assert result.published_at == datetime(2026, 9, 28, tzinfo=UTC)
    assert str(requests[0].url) == ALTERNATIVE_ME_FNG_ENDPOINT


def test_source_field_discloses_vendor_composite_paused_surveys_and_attribution() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=fear_greed_payload(),
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fear_greed_index(client=client)

    assert isinstance(result, AlternativeMeFearGreedOk)
    assert "alternative.me" in result.source_field
    assert "six-weight composite" in result.source_field
    assert "volatility 25%" in result.source_field
    assert "momentum/volume 25%" in result.source_field
    assert "social 15%" in result.source_field
    assert "surveys 15% currently paused" in result.source_field
    assert "dominance 10%" in result.source_field
    assert "Google Trends 10%" in result.source_field
    assert "Data provided by alternative.me" in result.source_field


def test_registry_cell_face_disclosure_matches_fear_greed_acceptance_copy() -> None:
    entry = next(entry for entry in load_registry().root if entry.key == "fear_greed_index")

    assert entry.vendor == "alternative.me"
    assert entry.endpoint == ALTERNATIVE_ME_FNG_ENDPOINT
    assert entry.definable_for == ("MACRO",)
    assert entry.response_model == "alternative_me_fear_greed"
    assert entry.golden == "fixtures/alternative_me_fng.json"
    assert entry.required_bars == 1
    assert entry.parameters == {}
    assert "alternative.me" in entry.source_field
    assert "six-weight composite" in entry.source_field
    assert "surveys 15% currently paused" in entry.source_field
    assert "Data provided by alternative.me" in entry.source_field


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = fear_greed_payload()
    payload["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AlternativeMeFearGreedResponse.model_validate(payload)

    renamed = fear_greed_payload()
    row = renamed["data"][0]  # type: ignore[index]
    row["index_value"] = row.pop("value")  # type: ignore[attr-defined]
    with pytest.raises(ValidationError, match="value"):
        AlternativeMeFearGreedResponse.model_validate(renamed)

    retyped = fear_greed_payload()
    retyped["data"][0]["value"] = 70  # type: ignore[index]
    with pytest.raises(ValidationError, match="string_type"):
        AlternativeMeFearGreedResponse.model_validate(retyped)


def test_time_until_update_is_optional_for_older_rows() -> None:
    payload = fear_greed_payload()
    payload["data"].append(  # type: ignore[attr-defined]
        {
            "value": "66",
            "value_classification": "Greed",
            "timestamp": "1790467200",
        }
    )

    parsed = AlternativeMeFearGreedResponse.model_validate(payload)

    assert parsed.data[0].time_until_update == "74231"
    assert parsed.data[1].time_until_update is None


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = fear_greed_payload()
    payload["data"][0]["value"] = 70  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fear_greed_index(client=client)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "value" in result.detail


def _daily_keys_except_fear_greed() -> tuple[str, ...]:
    return tuple(
        entry.key
        for entry in load_registry().root
        if entry.expected_update_interval_seconds == 86400
        and entry.key != "fear_greed_index"
    )


def test_daily_board_assembles_fear_greed_fetcher_from_registry_slot() -> None:
    result = AlternativeMeFearGreedOk(
        value=70,
        source_timestamp=datetime(2026, 9, 28, tzinfo=UTC),
        reference_period="2026-09-28",
        published_at=datetime(2026, 9, 28, tzinfo=UTC),
        value_classification="Greed",
    )

    run = run_all_assets(
        tier="daily",
        fetch_fear_greed=lambda: result,
        excluded_indicator_keys=_daily_keys_except_fear_greed(),
    )

    assert run.history == {}
    assert run.indicators == {"fear_greed_index": result}


@pytest.mark.integration
def test_live_daily_board_assembled_alternative_me_request_returns_real_fear_greed_value() -> None:
    run = run_all_assets(
        tier="daily",
        excluded_indicator_keys=_daily_keys_except_fear_greed(),
    )

    result = run.indicators["fear_greed_index"]
    assert isinstance(result, AlternativeMeFearGreedOk), result
    assert isinstance(result.value, int)
    assert 0 <= result.value <= 100
    assert result.reference_period
    assert result.source_timestamp.tzinfo is not None
    assert result.source_timestamp <= datetime.now(UTC)
