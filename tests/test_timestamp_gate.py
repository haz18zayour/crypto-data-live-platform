from datetime import UTC, datetime, timedelta

import pytest

from ingest.corroborate import TimestampMismatch, gate_timestamp_comparison

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)
SOURCE_TIMESTAMP = datetime(2026, 9, 9, tzinfo=UTC)


def test_unequal_source_timestamps_produce_no_divergence_at_all() -> None:
    comparisons = 0

    def compare() -> float:
        nonlocal comparisons
        comparisons += 1
        return 12.5

    result = gate_timestamp_comparison(
        SOURCE_TIMESTAMP - timedelta(days=1),
        SOURCE_TIMESTAMP,
        compare=compare,
        now=NOW,
    )

    assert isinstance(result, TimestampMismatch)
    assert comparisons == 0
    assert not hasattr(result, "divergence_bps")


def test_unequal_timestamps_name_both_timestamps_in_a_distinct_outcome() -> None:
    source_a_timestamp = SOURCE_TIMESTAMP - timedelta(days=1)
    source_b_timestamp = SOURCE_TIMESTAMP

    result = gate_timestamp_comparison(
        source_a_timestamp,
        source_b_timestamp,
        compare=lambda: 12.5,
        now=NOW,
    )

    assert result == TimestampMismatch(
        source_a_timestamp=source_a_timestamp,
        source_b_timestamp=source_b_timestamp,
    )
    assert result.outcome == "TIMESTAMP_MISMATCH"


def test_equal_timestamps_proceed_to_comparison() -> None:
    compared = object()

    result = gate_timestamp_comparison(
        SOURCE_TIMESTAMP,
        SOURCE_TIMESTAMP,
        compare=lambda: compared,
        now=NOW,
    )

    assert result is compared


@pytest.mark.parametrize("misaligned_source", ["source_a", "source_b"])
def test_each_source_must_be_on_a_utc_midnight_boundary(
    misaligned_source: str,
) -> None:
    source_a_timestamp = SOURCE_TIMESTAMP
    source_b_timestamp = SOURCE_TIMESTAMP
    if misaligned_source == "source_a":
        source_a_timestamp += timedelta(hours=1)
    else:
        source_b_timestamp += timedelta(hours=1)

    with pytest.raises(ValueError, match=rf"{misaligned_source}.*UTC midnight"):
        gate_timestamp_comparison(
            source_a_timestamp,
            source_b_timestamp,
            compare=lambda: pytest.fail("comparison must not run"),
            now=NOW,
        )


@pytest.mark.parametrize("future_source", ["source_a", "source_b"])
def test_comparison_is_refused_when_either_timestamp_is_in_the_future(
    future_source: str,
) -> None:
    source_a_timestamp = SOURCE_TIMESTAMP
    source_b_timestamp = SOURCE_TIMESTAMP
    if future_source == "source_a":
        source_a_timestamp = NOW + timedelta(hours=12)
    else:
        source_b_timestamp = NOW + timedelta(hours=12)

    with pytest.raises(ValueError, match=rf"{future_source}.*future"):
        gate_timestamp_comparison(
            source_a_timestamp,
            source_b_timestamp,
            compare=lambda: pytest.fail("comparison must not run"),
            now=NOW,
        )
