import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ingest.fetchers.okx import ENDPOINT, fetch_btc_daily_close
from ingest.status import Error, Ok, Reason, Result

FIXTURE_DIR = Path(__file__).parent / "fixtures"
RECORDED_OKX_RESPONSE = "okx_candles_2024-02-22.json"
MALFORMED_OKX_RESPONSE = "okx_candles_malformed.json"
NOW = datetime(2024, 2, 23, tzinfo=UTC)


def load_recording(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as fixture:
        return json.load(fixture)


def replay(name: str) -> tuple[dict[str, Any], Result]:
    recording = load_recording(name)
    recorded_response = recording["response"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ENDPOINT
        return httpx.Response(
            recorded_response["status_code"],
            json=recorded_response["body"],
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    return recording, result


def test_a_recorded_okx_candle_payload_parses_to_expected_value_and_timestamp() -> None:
    recording, result = replay(RECORDED_OKX_RESPONSE)

    assert recording["recording"]["kind"] == "captured"
    assert result == Ok(
        value=51_848.0,
        source_timestamp=datetime(2024, 2, 22, tzinfo=UTC),
    )


def test_the_recorded_payload_includes_an_unclosed_candle_and_it_is_excluded() -> None:
    recording, result = replay(RECORDED_OKX_RESPONSE)
    rows = recording["response"]["body"]["data"]

    assert rows[0][8] == "0"
    assert rows[0][4] == "51677.9"
    assert isinstance(result, Ok)
    assert result.value == 51_848.0
    assert result.value != float(rows[0][4])


def test_a_fixture_whose_recorded_status_is_error_produces_error_not_ok() -> None:
    recording, result = replay(MALFORMED_OKX_RESPONSE)

    assert recording["expected_status"] == "ERROR"
    assert isinstance(result, Error)
    assert not isinstance(result, Ok)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


@pytest.mark.parametrize(
    "name", [RECORDED_OKX_RESPONSE, MALFORMED_OKX_RESPONSE]
)
def test_fixtures_are_loaded_from_disk_not_constructed_inline(name: str) -> None:
    fixture_path = FIXTURE_DIR / name

    assert fixture_path.is_file()
    assert load_recording(name)["response"]["body"]
