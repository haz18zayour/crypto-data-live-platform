from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.okx import fetch_btc_daily_close
from ingest.schemas import OkxCandleResponse
from ingest.status import Error, Reason

NOW = datetime(2026, 9, 8, 12, tzinfo=UTC)


def valid_payload() -> dict[str, object]:
    return {
        "code": "0",
        "msg": "",
        "data": [
            [
                str(int((NOW - timedelta(days=2)).timestamp() * 1000)),
                "1",
                "2",
                "0.5",
                "42.5",
                "10",
                "10",
                "10",
                "1",
            ]
        ],
    }


def test_an_unexpected_extra_field_is_rejected() -> None:
    payload = valid_payload()
    payload["unexpected"] = "vendor reshape"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        OkxCandleResponse.model_validate(payload)


def test_a_missing_expected_field_is_rejected() -> None:
    payload = valid_payload()
    del payload["msg"]

    with pytest.raises(ValidationError, match="msg"):
        OkxCandleResponse.model_validate(payload)


@pytest.mark.parametrize("changed_value", [79_111.8, None])
def test_a_type_change_is_rejected(changed_value: object) -> None:
    payload = valid_payload()
    data = payload["data"]
    assert isinstance(data, list)
    row = data[0]
    assert isinstance(row, list)
    row[4] = changed_value

    with pytest.raises(ValidationError, match="string_type"):
        OkxCandleResponse.model_validate(payload)


def test_a_rejected_payload_becomes_error_with_fetch_failed_never_ok() -> None:
    payload = valid_payload()
    payload["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]
