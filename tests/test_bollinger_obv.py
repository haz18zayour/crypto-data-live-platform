import json
import math
from pathlib import Path
from typing import Any, cast

import pytest

from ingest.indicators import bollinger_bands, obv
from ingest.registry import IndicatorDefinition, IndicatorRegistry

GOLDEN_DIRECTORY = Path(__file__).with_name("goldens") / "hand_computed"
BOLLINGER_GOLDEN_PATH = GOLDEN_DIRECTORY / "bollinger_20_2_population.json"
OBV_GOLDEN_PATH = GOLDEN_DIRECTORY / "obv_base_volume.json"
GOLDEN_PATHS = (BOLLINGER_GOLDEN_PATH, OBV_GOLDEN_PATH)
ABSOLUTE_TOLERANCE = 1e-12


def load_golden(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_bollinger_bands_match_a_hand_computed_20_period_population_stdev_golden() -> (
    None
):
    golden = load_golden(BOLLINGER_GOLDEN_PATH)
    closes = [bar["close"] for bar in golden["input_bars"]]
    expected = golden["expected"]

    assert len(closes) == golden["registry"]["required_bars"] == 20

    mean = sum(closes) / len(closes)
    squared_deviations = sum((close - mean) ** 2 for close in closes)
    population_stdev = math.sqrt(squared_deviations / len(closes))
    hand_computed = (
        mean + golden["parameters"]["deviations"] * population_stdev,
        mean,
        mean - golden["parameters"]["deviations"] * population_stdev,
    )
    actual = bollinger_bands(
        golden["input_bars"],
        period=golden["parameters"]["period"],
        deviations=golden["parameters"]["deviations"],
    )

    assert squared_deviations == pytest.approx(
        expected["population_stdev"] ** 2 * len(closes),
        abs=ABSOLUTE_TOLERANCE,
        rel=0.0,
    )
    assert population_stdev == pytest.approx(
        expected["population_stdev"], abs=ABSOLUTE_TOLERANCE, rel=0.0
    )
    assert hand_computed == pytest.approx(
        (expected["upper"], expected["middle"], expected["lower"]),
        abs=ABSOLUTE_TOLERANCE,
        rel=0.0,
    )
    assert actual == pytest.approx(hand_computed, abs=ABSOLUTE_TOLERANCE, rel=0.0)


def test_a_sample_stdev_implementation_fails_the_golden() -> None:
    golden = load_golden(BOLLINGER_GOLDEN_PATH)
    closes = [bar["close"] for bar in golden["input_bars"]]
    expected = golden["expected"]
    mean = sum(closes) / len(closes)
    squared_deviations = sum((close - mean) ** 2 for close in closes)
    sample_stdev = math.sqrt(squared_deviations / (len(closes) - 1))
    sample_bands = (
        mean + 2 * sample_stdev,
        mean,
        mean - 2 * sample_stdev,
    )

    with pytest.raises(AssertionError):
        assert sample_bands == pytest.approx(
            (expected["upper"], expected["middle"], expected["lower"]),
            abs=ABSOLUTE_TOLERANCE,
            rel=0.0,
        )


def test_obv_matches_a_hand_computed_golden_over_a_short_series() -> None:
    golden = load_golden(OBV_GOLDEN_PATH)

    actual = [
        obv(golden["input_bars"][:length])
        for length in range(1, len(golden["input_bars"]) + 1)
    ]

    assert golden["input_bars"][1]["close"] == golden["input_bars"][2]["close"]
    assert golden["input_bars"][2]["volume"] > 0
    assert actual == golden["expected_outputs"]
    assert actual[2] == actual[1]


def test_obv_uses_base_volume_and_the_registry_records_which() -> None:
    golden = load_golden(OBV_GOLDEN_PATH)
    bars = golden["input_bars"]
    with_changed_quote_volume = [
        {**bar, "quote_volume": bar["quote_volume"] * 1_000_000} for bar in bars
    ]

    assert obv(with_changed_quote_volume) == obv(bars)

    source_fields = golden["registry"]["source_fields"]
    definitions = IndicatorRegistry.model_validate(
        tuple(
            IndicatorDefinition(
                key=f"btc_obv_{venue}",
                vendor=venue,
                endpoint=f"https://{venue}.example.test/candles",
                source_field=source_field,
                definable_for=("BTC",),
                required_bars=golden["registry"]["required_bars"],
                frozen_after_observations=3,
                talib_function="OBV",
                derives_from="btc_obv_okx",
                parameters=golden["registry"]["parameters"],
                expected_update_interval_seconds=86_400,
                freshness_warn_seconds=108_000,
                freshness_stale_seconds=172_800,
                uncorroborated={"note": golden["registry"]["uncorroborated_note"]},
            )
            for venue, source_field in source_fields.items()
        )
    )

    assert {
        entry.vendor: entry.source_field for entry in definitions.root
    } == source_fields
    assert all("base" in entry.source_field for entry in definitions.root)
    assert "flat close OBV is unchanged" in golden["registry"]["uncorroborated_note"]


def test_each_golden_names_its_external_source_and_the_arithmetic_used() -> None:
    for path in GOLDEN_PATHS:
        golden = load_golden(path)

        assert golden["external"] is True
        assert golden["source"].strip()
        assert golden["source_url"].startswith("https://")
        assert golden["source_accessed"] == "2026-09-10"
        assert golden["source_convention"].strip()
        assert golden["arithmetic"]
