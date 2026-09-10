from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ingest import corroborate
from ingest.corroborate import (
    CorroborationOutcome,
    NotCorroboratedRecord,
    corroboration_is_failure,
    record_not_corroborated,
    run_live_corroboration,
)
from ingest.status import Error, Ok, Reason, Result, Unavailable

SOURCE_TIMESTAMP = datetime(2026, 9, 9, tzinfo=UTC)
OLDER_TIMESTAMP = SOURCE_TIMESTAMP - timedelta(days=1)


class _Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class RecordingConnection:
    def __init__(self) -> None:
        self.stored: tuple[object, ...] | None = None

    def transaction(self) -> Any:
        return nullcontext()

    def execute(
        self, statement: str, parameters: tuple[object, ...]
    ) -> _Cursor:
        if "insert into corroborations" in statement:
            if self.stored is not None:
                return _Cursor(None)
            datapoint_id, status, reason = parameters
            self.stored = (91, datapoint_id, reason, status)
            return _Cursor(self.stored)
        if "select id, datapoint_a_id" in statement:
            return _Cursor(self.stored)
        raise AssertionError(f"unexpected SQL: {statement}")


def _run_with_second_venue(
    monkeypatch: pytest.MonkeyPatch,
    second_venue: Result,
) -> tuple[CorroborationOutcome, list[Ok]]:
    persisted: list[Ok] = []

    def persist_primary(*args: object, **kwargs: object) -> int:
        result = kwargs["result"]
        assert isinstance(result, Ok)
        persisted.append(result)
        return 41

    monkeypatch.setattr(corroborate, "persist_datapoint", persist_primary)
    connection = RecordingConnection()
    result = run_live_corroboration(
        connection,  # type: ignore[arg-type]
        source_a_fetcher=lambda: Ok(
            value=78_300.70,
            source_timestamp=SOURCE_TIMESTAMP,
        ),
        source_b_fetcher=lambda: second_venue,
    )
    return result, persisted


def _older_second_venue_bar() -> Ok:
    return Ok(value=78_250.0, source_timestamp=OLDER_TIMESTAMP)


def test_a_missing_second_venue_bar_yields_not_corroborated_not_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, persisted = _run_with_second_venue(
        monkeypatch,
        _older_second_venue_bar(),
    )

    assert isinstance(result, NotCorroboratedRecord)
    assert result.status == "NOT_CORROBORATED"
    assert not isinstance(result, Error)
    assert persisted == [
        Ok(value=78_300.70, source_timestamp=SOURCE_TIMESTAMP)
    ]
    assert persisted[0].value == 78_300.70


def test_not_corroborated_is_distinct_from_a_second_venue_fetch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing, _ = _run_with_second_venue(
        monkeypatch,
        _older_second_venue_bar(),
    )
    failed, persisted = _run_with_second_venue(
        monkeypatch,
        Error(reason=Reason.FETCH_FAILED, detail="Coinbase returned HTTP 500"),
    )

    assert isinstance(missing, NotCorroboratedRecord)
    assert failed == Error(
        reason=Reason.FETCH_FAILED,
        detail="Coinbase returned HTTP 500",
    )
    assert persisted == []


def test_no_divergence_exists_when_there_is_nothing_to_compare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _run_with_second_venue(
        monkeypatch,
        _older_second_venue_bar(),
    )

    assert isinstance(result, NotCorroboratedRecord)
    assert not hasattr(result, "divergence_bps")
    assert not hasattr(result, "tolerance_bps_at_write")


def test_dead_mans_switch_does_not_fire_for_not_corroborated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing, _ = _run_with_second_venue(
        monkeypatch,
        _older_second_venue_bar(),
    )
    failed = Error(
        reason=Reason.FETCH_FAILED,
        detail="Coinbase returned HTTP 500",
    )

    assert not corroboration_is_failure(missing)
    assert corroboration_is_failure(failed)


def test_no_closed_second_venue_bars_is_also_not_corroborated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, persisted = _run_with_second_venue(
        monkeypatch,
        Unavailable(reason=Reason.FETCH_FAILED),
    )

    assert isinstance(result, NotCorroboratedRecord)
    assert len(persisted) == 1


def test_not_corroborated_reason_is_recorded_for_the_page() -> None:
    connection = RecordingConnection()

    result = record_not_corroborated(
        connection,  # type: ignore[arg-type]
        datapoint_id=41,
        reason=Reason.FETCH_FAILED,
    )

    assert result == NotCorroboratedRecord(
        id=91,
        datapoint_id=41,
        reason=Reason.FETCH_FAILED,
    )
    assert connection.stored == (
        91,
        41,
        Reason.FETCH_FAILED.value,
        "NOT_CORROBORATED",
    )
