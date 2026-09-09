import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from ingest.compute import compute_indicator, daily_close
from ingest.registry import IndicatorDefinition, load_registry

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens")
GOLDEN_PATHS = tuple(sorted(GOLDEN_DIRECTORY.glob("*.json")))


def load_golden(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def definition_for(golden: Mapping[str, Any]) -> IndicatorDefinition:
    indicator_key = golden["indicator_key"]
    return next(
        entry for entry in load_registry().root if entry.key == indicator_key
    )


def assert_matches_golden(
    golden: Mapping[str, Any],
    calculation: Callable[[Sequence[Mapping[str, float]]], float],
) -> None:
    actual = compute_indicator(
        definition_for(golden), golden["input_bars"], calculation
    )
    assert actual == golden["expected"]


def test_each_golden_file_records_where_its_expected_value_came_from() -> None:
    assert GOLDEN_PATHS, "no committed golden files found"

    for path in GOLDEN_PATHS:
        source = load_golden(path).get("source")
        assert isinstance(source, str) and source.strip(), (
            f"{path.name} has no expected-value provenance"
        )


def test_at_least_one_golden_per_indicator_family_is_externally_computed() -> None:
    goldens = [load_golden(path) for path in GOLDEN_PATHS]
    families = {golden["indicator_family"] for golden in goldens}
    external_families = {
        golden["indicator_family"]
        for golden in goldens
        if golden.get("external") is True
    }

    assert external_families == families


@pytest.mark.parametrize(
    "path", GOLDEN_PATHS, ids=lambda path: path.stem
)
def test_recomputing_from_the_stored_input_bars_reproduces_the_golden_exactly(
    path: Path,
) -> None:
    golden = load_golden(path)
    calculations = {"daily_close": daily_close}

    assert_matches_golden(golden, calculations[golden["calculation"]])


def test_a_changed_computation_fails_the_golden_rather_than_updating_it() -> None:
    path = GOLDEN_DIRECTORY / "btc_daily_close.json"
    contents_before = path.read_bytes()
    golden = load_golden(path)

    def changed_daily_close(bars: Sequence[Mapping[str, float]]) -> float:
        return daily_close(bars) + 1.0

    with pytest.raises(AssertionError):
        assert_matches_golden(golden, changed_daily_close)

    assert path.read_bytes() == contents_before
