from datetime import UTC, datetime

import httpx
import pytest

from ingest.fetchers import okx
from ingest.status import Error, Ok, Reason

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def candle(opened_at: datetime, close: str = "42.5") -> list[str]:
    return [
        str(int(opened_at.timestamp() * 1000)),
        "1",
        "2",
        "0.5",
        close,
        "10",
        "10",
        "10",
        "1",
    ]


def fetch(rows: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> Error | Ok:
    monkeypatch.setattr(okx, "REQUIRED_BARS", 3, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "0", "msg": "", "data": rows},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = okx.fetch_btc_daily_close(client=client, now=NOW)

    assert isinstance(result, (Error, Ok))
    return result


def test_a_response_with_fewer_bars_than_requested_returns_error_not_a_short_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        candle(datetime(2026, 9, 8, tzinfo=UTC), close="not-a-number"),
        candle(datetime(2026, 9, 7, tzinfo=UTC)),
    ]

    result = fetch(rows, monkeypatch)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "returned 2 bars, expected 3" in result.detail
    assert "not-a-number" not in result.detail


def test_a_gap_in_the_bar_sequence_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        candle(datetime(2026, 9, 8, tzinfo=UTC)),
        candle(datetime(2026, 9, 7, tzinfo=UTC)),
        candle(datetime(2026, 9, 5, tzinfo=UTC)),
    ]

    result = fetch(rows, monkeypatch)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "not contiguous" in result.detail


@pytest.mark.parametrize(
    "timestamps",
    [
        (
            datetime(2026, 9, 8, tzinfo=UTC),
            datetime(2026, 9, 7, tzinfo=UTC),
            datetime(2026, 9, 7, tzinfo=UTC),
        ),
        (
            datetime(2026, 9, 8, tzinfo=UTC),
            datetime(2026, 9, 6, tzinfo=UTC),
            datetime(2026, 9, 7, tzinfo=UTC),
        ),
    ],
    ids=["duplicate", "out-of-order"],
)
def test_bars_are_strictly_ordered_and_non_duplicated(
    timestamps: tuple[datetime, datetime, datetime],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = fetch([candle(timestamp) for timestamp in timestamps], monkeypatch)

    assert isinstance(result, Error)
    assert result.reason is Reason.FETCH_FAILED
    assert "not strictly ordered" in result.detail


def test_no_code_path_synthesises_pads_or_interpolates_a_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        candle(datetime(2026, 9, 8, tzinfo=UTC)),
        candle(datetime(2026, 9, 6, tzinfo=UTC)),
        candle(datetime(2026, 9, 5, tzinfo=UTC)),
    ]
    original_rows = [row.copy() for row in rows]

    result = fetch(rows, monkeypatch)

    assert isinstance(result, Error)
    assert rows == original_rows
    assert len(rows) == 3


def test_the_error_detail_names_how_many_bars_arrived_versus_how_many_were_expected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        candle(datetime(2026, 9, 8, tzinfo=UTC)),
        candle(datetime(2026, 9, 7, tzinfo=UTC)),
    ]

    result = fetch(rows, monkeypatch)

    assert isinstance(result, Error)
    assert result.detail == "OKX returned 2 bars, expected 3"
