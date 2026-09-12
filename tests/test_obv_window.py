import json
from pathlib import Path
from typing import Any

from ingest.indicators import obv
from ingest.registry import IndicatorDefinition, load_registry

GOLDEN_PATH = (
    Path(__file__).with_name("goldens") / "hand_computed" / "obv_base_volume.json"
)


def load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def obv_definitions() -> tuple[IndicatorDefinition, ...]:
    return tuple(
        definition
        for definition in load_registry().root
        if definition.talib_function == "OBV"
    )


def test_obv_declares_at_least_200_bars_with_product_reason() -> None:
    definitions = obv_definitions()

    assert len(definitions) == 4
    for definition in definitions:
        assert definition.required_bars is not None
        assert definition.required_bars >= 200
        assert definition.note is not None
        assert "cumulative" in definition.note.casefold()
        assert "daily bars" in definition.note.casefold()


def test_obv_declared_window_materially_changes_value_from_five_bars() -> None:
    definitions = obv_definitions()

    assert len(definitions) == 4
    for definition in definitions:
        required_bars = definition.required_bars
        assert required_bars is not None
        bars = [
            {"close": float(index), "volume": 100.0}
            for index in range(required_bars)
        ]

        declared_window_value = obv(bars)
        five_bar_value = obv(bars[-5:])

        assert abs(declared_window_value - five_bar_value) >= 10 * abs(five_bar_value)


def test_obv_hand_computed_golden_still_passes_at_its_own_length() -> None:
    golden = load_golden()

    actual = [
        obv(golden["input_bars"][:length])
        for length in range(1, len(golden["input_bars"]) + 1)
    ]

    assert len(golden["input_bars"]) == 5
    assert actual == golden["expected_outputs"]
