import os
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from ingest.fetchers.fred import (
    EARLIEST_REALTIME_START,
    FRED_SERIES_OBSERVATIONS_ENDPOINT,
    LATEST_REALTIME_END,
    FredOk,
    FredSeries,
    fetch_fred_series,
)
from ingest.schemas import FredSeriesObservationsResponse
from ingest.status import Error, Reason


def fred_payload(
    observations: list[dict[str, str]],
    *,
    output_type: int = 4,
) -> dict[str, object]:
    return {
        "realtime_start": EARLIEST_REALTIME_START,
        "realtime_end": LATEST_REALTIME_END,
        "observation_start": "1776-07-04",
        "observation_end": "9999-12-31",
        "units": "lin",
        "output_type": output_type,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "desc",
        "count": len(observations),
        "offset": 0,
        "limit": 10,
        "observations": observations,
    }


def observation(
    *,
    realtime_start: str,
    date: str,
    value: str,
) -> dict[str, str]:
    return {
        "realtime_start": realtime_start,
        "realtime_end": "9999-12-31",
        "date": date,
        "value": value,
    }


def test_dot_observation_is_skipped_and_never_coerced_to_zero() -> None:
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-27",
                date="2026-09-27",
                value=".",
            ),
            observation(
                realtime_start="2026-09-24",
                date="2026-09-24",
                value="21.34",
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="VIXCLS"),
            client=client,
            api_key="test-key",
        )

    assert isinstance(result, FredOk)
    assert result.value == 21.34
    assert result.value != 0
    assert result.reference_period == "2026-09-24"
    assert result.published_at == datetime(2026, 9, 24, tzinfo=UTC)


def test_reference_period_is_observation_date_not_request_date() -> None:
    requested: list[httpx.Request] = []
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-11",
                date="2026-08-01",
                value="323.976",
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="CPIAUCSL"),
            client=client,
            api_key="test-key",
        )

    assert isinstance(result, FredOk)
    assert result.reference_period == "2026-08-01"
    assert result.published_at == datetime(2026, 9, 11, tzinfo=UTC)
    assert result.reference_period != "2026-09-27"
    request = requested[0]
    assert request.url.params["output_type"] == "4"
    assert request.url.params["realtime_start"] == EARLIEST_REALTIME_START
    assert request.url.params["realtime_end"] == LATEST_REALTIME_END


def test_revised_same_observation_date_is_disclosed_in_source_field() -> None:
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-11",
                date="2026-08-01",
                value="324.001",
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="CPIAUCSL"),
            client=client,
            api_key="test-key",
            previous_reference_period="2026-08-01",
            previous_observation_value="323.976",
        )

    assert isinstance(result, FredOk)
    assert result.reference_period == "2026-08-01"
    assert "revised from 323.976" in result.source_field


def test_same_value_for_same_observation_date_is_not_marked_as_revision() -> None:
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-11",
                date="2026-08-01",
                value="323.976",
            )
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="CPIAUCSL"),
            client=client,
            api_key="test-key",
            previous_reference_period="2026-08-01",
            previous_observation_value="323.976",
        )

    assert isinstance(result, FredOk)
    assert "revised from" not in result.source_field


def test_http_429_returns_fetch_failed_with_status_and_no_retry() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="DFF"),
            client=client,
            api_key="test-key",
        )

    assert requests == 1
    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "429" in result.detail
    with pytest.raises(AttributeError):
        _ = result.value  # type: ignore[attr-defined]


def test_response_model_rejects_added_renamed_or_retyped_fields() -> None:
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-24",
                date="2026-09-24",
                value="21.34",
            )
        ]
    )
    payload["unexpected"] = "vendor reshape"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FredSeriesObservationsResponse.model_validate(payload)

    renamed = fred_payload(
        [
            observation(
                realtime_start="2026-09-24",
                date="2026-09-24",
                value="21.34",
            )
        ]
    )
    row = renamed["observations"][0]  # type: ignore[index]
    row["published"] = row.pop("realtime_start")  # type: ignore[attr-defined]
    with pytest.raises(ValidationError, match="realtime_start"):
        FredSeriesObservationsResponse.model_validate(renamed)

    retyped = fred_payload(
        [
            observation(
                realtime_start="2026-09-24",
                date="2026-09-24",
                value="21.34",
            )
        ]
    )
    retyped["observations"][0]["value"] = 21.34  # type: ignore[index]
    with pytest.raises(ValidationError, match="string_type"):
        FredSeriesObservationsResponse.model_validate(retyped)


def test_malformed_response_becomes_fetch_failed_error() -> None:
    payload = fred_payload(
        [
            observation(
                realtime_start="2026-09-24",
                date="2026-09-24",
                value="21.34",
            )
        ]
    )
    payload["unexpected"] = "vendor reshape"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_fred_series(
            FredSeries(series_id="VIXCLS"),
            client=client,
            api_key="test-key",
        )

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "unexpected" in result.detail


@pytest.mark.integration
def test_live_fred_output_type_4_realtime_start_is_true_publication_date() -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY is required for the live FRED publication-date probe")

    default_request: httpx.Response
    initial_release_request: httpx.Response
    with httpx.Client(timeout=10) as client:
        default_request = client.get(
            FRED_SERIES_OBSERVATIONS_ENDPOINT,
            params={
                "series_id": "CPIAUCSL",
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "1",
            },
        )
        initial_release_request = client.get(
            FRED_SERIES_OBSERVATIONS_ENDPOINT,
            params={
                "series_id": "CPIAUCSL",
                "api_key": api_key,
                "file_type": "json",
                "output_type": "4",
                "realtime_start": EARLIEST_REALTIME_START,
                "realtime_end": LATEST_REALTIME_END,
                "order_by": "observation_date",
                "sort_order": "desc",
                "limit": "1",
            },
        )

    default_request.raise_for_status()
    initial_release_request.raise_for_status()
    default_row = default_request.json()["observations"][0]
    initial_release_row = initial_release_request.json()["observations"][0]

    assert default_row["date"] == initial_release_row["date"]
    # For a series whose latest observation has never been revised, a default (no
    # realtime params) query and an output_type=4 initial-release query return the SAME
    # realtime_start - there is only one vintage. They only diverge once a revision has
    # happened (default then reflects the latest vintage, output_type=4 still the first).
    # Confirmed live, 2026-09-27: CPIAUCSL's current observation has not yet been revised,
    # so this assertion must tolerate equality, not require strict inequality.
    assert initial_release_row["realtime_start"] <= default_row["realtime_start"]
    fetcher_result = fetch_fred_series(FredSeries(series_id="CPIAUCSL"))
    assert isinstance(fetcher_result, FredOk), fetcher_result
    assert fetcher_result.published_at == (
        datetime.fromisoformat(initial_release_row["realtime_start"]).replace(tzinfo=UTC)
    )
