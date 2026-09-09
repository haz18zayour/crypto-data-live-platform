import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.status import Error, Ok, Reason, Stale, Unavailable


def test_unavailable_and_error_expose_no_numeric_value() -> None:
    results = (
        Unavailable(reason=Reason.NOT_FETCHED),
        Error(reason=Reason.FETCH_FAILED, detail="request timed out"),
    )

    for result in results:
        with pytest.raises(AttributeError):
            _ = result.value  # type: ignore[union-attr]


def test_ok_cannot_be_constructed_without_a_source_timestamp() -> None:
    with pytest.raises(TypeError):
        Ok(value=1.0)  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        Ok(value=1.0, source_timestamp=None)  # type: ignore[arg-type]


def test_absence_reason_is_required_and_limited_to_the_declared_reasons() -> None:
    assert {reason.value for reason in Reason} == {
        "NOT_DEFINABLE",
        "PAYWALLED",
        "FETCH_FAILED",
        "NOT_FETCHED",
    }

    with pytest.raises(TypeError):
        Unavailable()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Error(detail="request timed out")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Unavailable(reason="UNKNOWN")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Error(reason="UNKNOWN", detail="bad response")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("result", "field", "replacement"),
    [
        (
            Ok(value=1.0, source_timestamp=datetime(2026, 1, 1, tzinfo=UTC)),
            "value",
            2.0,
        ),
        (
            Stale(value=1.0, source_timestamp=datetime(2026, 1, 1, tzinfo=UTC)),
            "source_timestamp",
            datetime(2026, 1, 2, tzinfo=UTC),
        ),
        (
            Unavailable(reason=Reason.NOT_DEFINABLE),
            "reason",
            Reason.PAYWALLED,
        ),
        (
            Error(reason=Reason.FETCH_FAILED, detail="request timed out"),
            "detail",
            "different failure",
        ),
    ],
)
def test_results_are_immutable(
    result: object,
    field: str,
    replacement: object,
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(result, field, replacement)
